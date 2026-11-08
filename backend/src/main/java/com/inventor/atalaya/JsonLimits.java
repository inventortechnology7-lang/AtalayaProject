package com.inventor.atalaya;
import com.fasterxml.jackson.core.StreamReadConstraints;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.*;
@Configuration
class JsonLimits {
 @Bean Jackson2ObjectMapperBuilderCustomizer boundedJson(){
  return builder -> builder.postConfigurer(mapper -> mapper.getFactory().setStreamReadConstraints(
   StreamReadConstraints.builder().maxDocumentLength(1048576).maxStringLength(65536).maxNestingDepth(20).build()));
 }
}
