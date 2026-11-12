"""Repair CARTO build configuration on the existing private ERP deployment.

Run from Windows: python scripts/repair-vps-maps.py
Uses the existing pinned SSH host key and encrypted administrator credential.
Does not change application code, databases, network rules, or backend services.
"""

import ast
import json
from pathlib import Path
import sys


BUILD_BEFORE = "if kind=='frontend':cmd+=['--build-arg','PUBLIC_API_URL=']"
BUILD_AFTER = (
    "if kind=='frontend':cmd+=['--build-arg','PUBLIC_API_URL=',"
    "'--build-arg','PUBLIC_CARTO_BASEMAP_API_KEY='+"
    "read(DEPLOY/'frontend-public.json')['PUBLIC_CARTO_BASEMAP_API_KEY']]"
)


def patch_builder(source):
    if BUILD_AFTER in source:
        return source
    if source.count(BUILD_BEFORE) != 1:
        raise ValueError('El actualizador cambió; no se modificará automáticamente.')
    result = source.replace(BUILD_BEFORE, BUILD_AFTER)
    ast.parse(result)
    return result


def read_carto_key(path):
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        name, separator, value = line.strip().partition('=')
        if separator and name == 'PUBLIC_CARTO_BASEMAP_API_KEY':
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                return value
    raise ValueError('Falta PUBLIC_CARTO_BASEMAP_API_KEY en el .env local.')


REMOTE = r'''
import copy, fcntl, importlib.util, json, os, re, subprocess, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

payload = json.load(sys.stdin)
root = Path('/srv/erp')
deploy = root / 'deploy'
stamp = str(time.time_ns())
with (deploy / 'lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (deploy / 'pending.json').exists():
        raise RuntimeError('Hay una actualización pendiente; recupérela antes de reparar mapas.')
    updater = deploy / 'deploy_guest.py'
    original = updater.read_text()
    if payload['after'] in original:
        patched = original
    elif original.count(payload['before']) == 1:
        patched = original.replace(payload['before'], payload['after'])
    else:
        raise RuntimeError('El actualizador remoto cambió; se canceló sin modificarlo.')
    compile(patched, str(updater), 'exec')
    key = payload['key']
    print('Verificando acceso a CARTO para gestionasv.lat...', flush=True)
    url = 'https://a.basemaps.cartocdn.com/light_all/0/0/0.png?' + urlencode({'key': key})
    with urlopen(Request(url, headers={'Referer': 'https://gestionasv.lat/'}), timeout=30) as response:
        if response.status != 200 or not response.headers.get('Content-Type', '').startswith('image/'):
            raise RuntimeError('CARTO no devolvió un mosaico válido para el dominio de producción.')
    spec = importlib.util.spec_from_file_location('erp_deploy', updater)
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    sha = d.valid_sha(d.read(deploy / 'deployed.json')['sha'])
    source = root / 'releases' / sha / 'frontend'
    if not (source / 'Dockerfile').is_file():
        raise RuntimeError('No se encontró el código de la versión instalada; se canceló la reparación.')
    image = 'erp-maps-repair:' + stamp
    print('Compilando únicamente el frontend; el ERP sigue disponible...', flush=True)
    log_path = deploy / ('maps-build-' + stamp + '.log')
    env = os.environ.copy()
    env['PUBLIC_CARTO_BASEMAP_API_KEY'] = key
    with log_path.open('w') as log:
        os.chmod(log_path, 0o600)
        subprocess.run(['docker', 'build', '--target', 'prod', '--build-arg', 'PUBLIC_API_URL=',
                        '--build-arg', 'PUBLIC_CARTO_BASEMAP_API_KEY',
                        '--label', 'org.opencontainers.image.revision=' + sha,
                        '-t', image, str(source)], env=env, stdout=log, stderr=log, check=True)
    # Check the browser bundle itself, rather than merely the container environment.
    check = "const fs=require('fs');const k=process.env.PUBLIC_CARTO_BASEMAP_API_KEY;function scan(p){return fs.readdirSync(p,{withFileTypes:true}).some(e=>e.isDirectory()?scan(p+'/'+e.name):e.name.endsWith('.js')&&fs.readFileSync(p+'/'+e.name,'utf8').includes(k))}if(!scan('/app/build/client'))process.exit(1)"
    subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                    '-e', 'PUBLIC_CARTO_BASEMAP_API_KEY', '--entrypoint', 'node',
                    image, '-e', check], env=env, check=True)
    config = d.read(root / 'compose.json')
    candidate = copy.deepcopy(config)
    candidate['services']['frontend']['image'] = image
    # Keep rollback material and persist the public build setting outside Git.
    backup = deploy / ('maps-backup-' + stamp)
    backup.mkdir(mode=0o700)
    d.write(backup / 'compose.json', config)
    (backup / 'deploy_guest.py').write_text(original)
    d.write(deploy / 'frontend-public.json', {'PUBLIC_CARTO_BASEMAP_API_KEY': key})
    temporary = updater.with_suffix('.maps-tmp')
    temporary.write_text(patched)
    os.chmod(temporary, updater.stat().st_mode & 0o777)
    temporary.replace(updater)
    print('Activando el frontend corregido...', flush=True)
    try:
        d.sync_panel(candidate)
        d.compose('up', '-d', '--no-deps', 'frontend')
        d.wait_ready()
    except Exception:
        print('La verificación falló; recuperando el frontend anterior.', flush=True)
        d.sync_panel(config)
        d.compose('up', '-d', '--no-deps', 'frontend')
        d.wait_ready()
        raise
    d.write(deploy / 'maps-repair.json', {'sha': sha, 'image': image, 'time': time.time(),
                                        'bundle_verified': True, 'carto_tile_verified': True})
    print('Mapas reparados. Frontend saludable; actualizaciones futuras configuradas.', flush=True)
'''


def main():
    sys.dont_write_bytecode = True
    tools = Path(r'D:\VPS-Local\Herramientas')
    erp_tools = Path(r'D:\VPS-Local\ERP\herramientas')
    sys.path[:0] = [str(tools), str(erp_tools)]
    import control
    import auto_update
    import ctypes
    import shlex

    key = read_carto_key(Path(__file__).resolve().parents[1] / '.env')
    local_updater = erp_tools / 'deploy_guest.py'
    original = local_updater.read_text(encoding='utf-8')
    patched = patch_builder(original)
    handle, available = auto_update.mutex()
    try:
        if not available:
            raise RuntimeError('Hay una actualización en curso. Espere a que finalice y vuelva a ejecutar.')
        client = control.connect()
        try:
            stdin, stdout, stderr = client.exec_command('sudo python3 -u -c ' + shlex.quote(REMOTE), timeout=3600)
            stdin.write(json.dumps({'key': key, 'before': BUILD_BEFORE, 'after': BUILD_AFTER}))
            stdin.flush()
            stdin.channel.shutdown_write()
            for line in stdout:
                print(line.rstrip().replace(key, '[CARTO]'), flush=True)
            error = stderr.read().decode(errors='replace').replace(key, '[CARTO]')
            if stdout.channel.recv_exit_status():
                raise RuntimeError(error[-3000:] or 'Falló la reparación remota.')
        finally:
            client.close()
        # Keep the Windows copy consistent with the installed updater.
        if patched != original:
            backup = local_updater.with_suffix('.py.before-maps')
            if not backup.exists():
                backup.write_text(original, encoding='utf-8')
            local_updater.write_text(patched, encoding='utf-8')
        print('Recargue https://gestionasv.lat/branches con Ctrl+F5.')
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('No se completó la reparación: ' + str(exc), file=sys.stderr)
        sys.exit(1)
