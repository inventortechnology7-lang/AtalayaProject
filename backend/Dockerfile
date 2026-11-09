FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
COPY src src
COPY Healthcheck.java .
RUN javac Healthcheck.java
RUN mvn -B package -DskipTests
FROM eclipse-temurin:21-jre-noble
WORKDIR /app
COPY --from=build /src/target/katana-1.0.0.jar app.jar
COPY --from=build /src/Healthcheck.class /app/Healthcheck.class
USER 10001:10001
EXPOSE 8080 8300
ENTRYPOINT ["java","-jar","app.jar"]
