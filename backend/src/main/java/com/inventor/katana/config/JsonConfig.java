package com.inventor.katana.config;
import com.fasterxml.jackson.core.StreamReadConstraints;
import io.swagger.v3.oas.annotations.OpenAPIDefinition;
import io.swagger.v3.oas.annotations.info.Info;
import io.swagger.v3.oas.annotations.security.*;
import io.swagger.v3.oas.annotations.enums.SecuritySchemeType;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.*;
@Configuration
@OpenAPIDefinition(info=@Info(title="Katana Local API",version="1.0",description="Supervisión local. Sin operaciones físicas."),security=@SecurityRequirement(name="localSession"))
@SecurityScheme(name="localSession",type=SecuritySchemeType.HTTP,scheme="bearer",bearerFormat="opaque session")
public class JsonConfig {
 @Bean Jackson2ObjectMapperBuilderCustomizer limits(){return builder->builder.postConfigurer(mapper->mapper.getFactory().setStreamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(32).maxStringLength(16384).maxNumberLength(100).maxDocumentLength(65536).build()));}
}
