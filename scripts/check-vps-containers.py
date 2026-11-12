"""Read-only inspection of live ERP container boundaries and database privileges.

Run with: python -B scripts/check-vps-containers.py
Uses existing pinned SSH identity. Does not print environment variables or secrets.
"""
import json
import shlex
import sys


REMOTE = r'''
import asyncio, json, socket, subprocess

PROJECT = 'qe6mnnekgdfazmhqjbv9qinf'
def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=45)
def inspect(name):
    return json.loads(docker('inspect', name))[0]

coolify = inspect('coolify')
admin_networks = set(coolify['NetworkSettings']['Networks'])
services = {}
objects = {}
for name in ['backend', 'frontend', 'web', 'db', 'redis', 'rustfs']:
    c = inspect(name + '-' + PROJECT)
    objects[name] = c
    h = c['HostConfig']
    mounts = [{'type':m['Type'], 'source':m['Source'], 'target':m['Destination'],
               'read_only':not m['RW']} for m in c['Mounts']]
    services[name] = {
        'running': c['State']['Running'],
        'configured_user': c['Config'].get('User') or '(image default/root)',
        'privileged': h['Privileged'],
        'host_network': h['NetworkMode'] == 'host',
        'host_pid_namespace': h.get('PidMode') == 'host',
        'cap_add': h.get('CapAdd') or [], 'cap_drop':h.get('CapDrop') or [],
        'security_options':h.get('SecurityOpt') or [],
        'read_only_root':h.get('ReadonlyRootfs', False),
        'memory_limit_bytes':h.get('Memory', 0),
        'cpu_limit_nanos':h.get('NanoCpus', 0),
        'pids_limit':h.get('PidsLimit'),
        'mounts':mounts,
        'docker_socket_mounted':any('docker.sock' in m['source'] or 'docker.sock' in m['target'] for m in mounts),
        'networks':list(c['NetworkSettings']['Networks']),
        'shares_coolify_network':bool(set(c['NetworkSettings']['Networks']) & admin_networks),
        'published_ports':h.get('PortBindings') or {},
    }

backend = 'backend-' + PROJECT
services['backend']['effective_user'] = docker('exec', backend, 'id').strip()
services['frontend']['effective_user'] = docker('exec', 'frontend-' + PROJECT, 'id').strip()

# Run SELECT using the application's real connection, not the postgres administrator CLI.
query = """import asyncio,json
from sqlalchemy import text
from app.infrastructure.db.session import async_session_factory
async def main():
 async with async_session_factory() as db:
  row=(await db.execute(text('SELECT rolname,rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user'))).mappings().one()
  print(json.dumps(dict(row)))
asyncio.run(main())
"""
role = json.loads(docker('exec', backend, 'python', '-c', query))

# A successful connection shows reachability only; it does not imply authentication bypass.
targets = set()
for network in objects['backend']['NetworkSettings']['Networks'].values():
    if network.get('Gateway'):
        for port in [22, 8000, 2375, 2376]:
            targets.add((network['Gateway'], port))
for network in coolify['NetworkSettings']['Networks'].values():
    if network.get('IPAddress'):
        targets.add((network['IPAddress'], 8080))
        targets.add((network['IPAddress'], 8000))
probe = """import socket,json
targets=__TARGETS__
out=[]
for host,port in targets:
 s=socket.socket();s.settimeout(1)
 try: reachable=s.connect_ex((host,port))==0
 except OSError: reachable=False
 finally: s.close()
 out.append({'host':host,'port':port,'reachable':reachable})
print(json.dumps(out))
""".replace('__TARGETS__', repr(sorted(targets)))
reachability = json.loads(docker('exec', backend, 'python', '-c', probe))
print(json.dumps({'services':services, 'backend_database_role':role,
                  'backend_management_reachability':reachability}, indent=2))
'''


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, r'D:\VPS-Local\Herramientas')
    import control
    client = control.connect()
    try:
        _, out, err = client.exec_command('sudo python3 -c ' + shlex.quote(REMOTE), timeout=180)
        result = out.read().decode(errors='replace')
        error = err.read().decode(errors='replace')
        if out.channel.recv_exit_status():
            raise RuntimeError(error[-2000:] or 'Remote inspection failed.')
        # Only the explicitly selected safe fields are returned by REMOTE.
        print(json.dumps(json.loads(result), indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Inspection incomplete: ' + str(exc), file=sys.stderr)
        sys.exit(1)
