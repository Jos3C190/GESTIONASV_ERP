FROM amazoncorretto:21-alpine-jdk

VOLUME /tmp

COPY target/*-exec.jar app.jar

ENV TZ=America/El_Salvador

ENTRYPOINT ["java", "--add-opens", "java.base/java.math=ALL-UNNAMED", "--add-opens", "java.base/java.time=ALL-UNNAMED", "-jar", "/app.jar"]