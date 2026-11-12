"""Enable the tracking simulator without changing production mode.

Run from Windows; pass --disable to turn the feature back off.
The local config change must also reach develop to survive future image builds.
"""
import argparse
import ast
import ctypes
import json
import shlex
import sys


OLD_FIELD = '    TRACKING_SIMULATOR_ENABLED: bool = False'
NEW_FIELD = OLD_FIELD + '\n    TRACKING_SIMULATOR_ALLOW_PRODUCTION: bool = False'
OLD_RULE = '        return self.TRACKING_SIMULATOR_ENABLED and not self.is_production'
NEW_RULE = '''        return self.TRACKING_SIMULATOR_ENABLED and (
            not self.is_production or self.TRACKING_SIMULATOR_ALLOW_PRODUCTION
        )'''


def patch_settings(source):
    if NEW_FIELD in source and NEW_RULE in source:
        return source
    if source.count(OLD_FIELD) != 1 or source.count(OLD_RULE) != 1:
        raise ValueError('La configuración instalada cambió; se canceló sin modificarla.')
    if 'TRACKING_SIMULATOR_ALLOW_PRODUCTION' in source:
        raise ValueError('La opción de producción ya existe con otra implementación.')
    result = source.replace(OLD_FIELD, NEW_FIELD).replace(OLD_RULE, NEW_RULE)
    ast.parse(result)
    return result


REMOTE = r'''
import ast, copy, fcntl, importlib.util, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
p=json.load(sys.stdin)
root=Path('/srv/erp');deploy=root/'deploy'
def capture(*args):
 return subprocess.check_output(['docker',*args],text=True,timeout=60)
with (deploy/'lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (deploy/'pending.json').exists():raise RuntimeError('Hay un despliegue pendiente de recuperar.')
 spec=importlib.util.spec_from_file_location('erp_deploy',deploy/'deploy_guest.py')
 d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
 old=d.read(root/'compose.json');candidate=copy.deepcopy(old)
 services=['backend','tracking-monitor']
 for name in services:
  if name not in old['services']:raise RuntimeError('Falta el servicio '+name)
 image=old['services']['backend']['image']
 if p['enabled']:
  print('Preparando la opción del simulador sobre la imagen instalada...',flush=True)
  source=capture('run','--rm','--network','none','--entrypoint','python',image,'-c',"from pathlib import Path; print(Path('/app/app/core/config.py').read_text(),end='')")
  if p['new_field'] not in source or p['new_rule'] not in source:
   if source.count(p['old_field'])!=1 or source.count(p['old_rule'])!=1 or 'TRACKING_SIMULATOR_ALLOW_PRODUCTION' in source:
    raise RuntimeError('La imagen tiene una configuración diferente; no se modificó.')
   source=source.replace(p['old_field'],p['new_field']).replace(p['old_rule'],p['new_rule'])
  ast.parse(source)
  user=json.loads(capture('image','inspect',image))[0]['Config']['User']
  if not user or not re.fullmatch(r'[A-Za-z0-9_:-]+',user):raise RuntimeError('Usuario de imagen inesperado.')
  tag='erp-tracking-demo:'+str(time.time_ns())
  with tempfile.TemporaryDirectory(prefix='tracking-build-',dir=deploy) as folder:
   folder=Path(folder)
   (folder/'config.py').write_text(source)
   if not re.fullmatch(r'[A-Za-z0-9_./:@-]+',image):raise RuntimeError('Referencia de imagen inesperada.')
   (folder/'Dockerfile').write_text('FROM '+image+'\nUSER root\nCOPY config.py /app/app/core/config.py\nUSER '+user+'\n')
   with (deploy/'tracking-demo-build.log').open('w') as log:
    os.chmod(deploy/'tracking-demo-build.log',0o600)
    subprocess.run(['docker','build','-t',tag,str(folder)],stdout=log,stderr=log,check=True,timeout=300)
  for name in services:
   if old['services'][name]['image']!=image:raise RuntimeError('Backend y monitor usan imágenes distintas; requiere revisión.')
   candidate['services'][name]['image']=tag
 for name in services:
  env=candidate['services'][name].setdefault('environment',{})
  if not isinstance(env,dict):raise RuntimeError('Formato de variables inesperado.')
  env['TRACKING_SIMULATOR_ENABLED']='true' if p['enabled'] else 'false'
  env['TRACKING_SIMULATOR_ALLOW_PRODUCTION']='true' if p['enabled'] else 'false'
 stamp=str(time.time_ns())
 d.write(deploy/('tracking-before-'+stamp+'.json'),old)
 check="from app.core.config import settings as s; import json; print(json.dumps({'production':s.is_production,'debug':s.DEBUG,'secure_cookies':s.SECURE_COOKIES,'simulator':s.simulator_enabled,'gps_configured':bool(s.TRACCAR_URL and s.TRACCAR_USER and s.TRACCAR_PASSWORD)}))"
 print('Activando backend y monitor GPS...',flush=True)
 try:
  d.sync_panel(candidate)
  d.compose('up','-d','--no-deps',*services)
  d.wait_ready()
  for name in services:
   state=json.loads(capture('exec',d.container(name),'python','-c',check))
   if not state['production'] or state['debug'] or state['simulator']!=p['enabled']:
    raise RuntimeError('No se confirmó la configuración de '+name)
   if name=='backend' and not state['secure_cookies']:raise RuntimeError('Cookies seguras desactivadas.')
   if p['enabled'] and not state['gps_configured']:raise RuntimeError('Traccar no está configurado.')
   print(name+': '+json.dumps(state),flush=True)
 except Exception:
  print('Recuperando configuración anterior...',flush=True)
  d.sync_panel(old);d.compose('up','-d','--no-deps',*services);d.wait_ready()
  raise
 d.write(deploy/'tracking-demo.json',{'enabled':p['enabled'],'time':time.time()})
 print('Simulador '+('habilitado' if p['enabled'] else 'deshabilitado')+'; ERP permanece en producción.',flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path[:0] = [r'D:\VPS-Local\Herramientas', r'D:\VPS-Local\ERP\herramientas']
    import control
    import auto_update

    handle, available = auto_update.mutex()
    try:
        if not available:
            raise RuntimeError('Hay una actualización en curso. Espere antes de reintentar.')
        client = control.connect()
        try:
            stdin, out, err = client.exec_command('sudo python3 -u -c ' + shlex.quote(REMOTE), timeout=900)
            stdin.write(json.dumps(dict(enabled=not args.disable, old_field=OLD_FIELD,
                                        new_field=NEW_FIELD, old_rule=OLD_RULE, new_rule=NEW_RULE)))
            stdin.flush()
            stdin.channel.shutdown_write()
            for line in out:
                print(line.rstrip(), flush=True)
            error = err.read().decode(errors='replace')
            if out.channel.recv_exit_status():
                raise RuntimeError(error[-2000:] or 'No se completó la activación.')
        finally:
            client.close()
        print('Recargue Seguimiento con Ctrl+F5.')
        print('Para conservar la función tras futuras actualizaciones, publique los cambios locales en develop.')
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
