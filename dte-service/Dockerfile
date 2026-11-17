FROM node:22-slim

# fecEmi/horEmi se calculan con Intl en America/El_Salvador (utils/fechaHoraSV.js);
# TZ solo alinea los registros del contenedor con la hora local.
ENV NODE_ENV=production \
    TZ=America/El_Salvador

WORKDIR /app

# Dependencias exactas del lockfile, sin las de desarrollo.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

# Solo el código de la aplicación: nunca .env, certificados ni la base local.
COPY src ./src
COPY scripts ./scripts

# El despliegue hace el checkout con umask 077, así que los archivos que cambia
# llegan en 600. Se dejan legibles (no escribibles) para `node`; si no, el
# contenedor falla con EACCES al abrir src/server.js.
RUN chmod -R a+rX /app/src /app/scripts /app/package.json /app/package-lock.json \
  && mkdir -p /app/data && chown -R node:node /app/data
USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "src/server.js"]
