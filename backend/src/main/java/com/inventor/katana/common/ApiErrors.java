package com.inventor.katana.common;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.dao.DataIntegrityViolationException;
@RestControllerAdvice
public class ApiErrors {
 @ExceptionHandler(ResponseStatusException.class) ResponseEntity<?> status(ResponseStatusException e) { return ResponseEntity.status(e.getStatusCode()).body(Map.of("error",e.getReason()==null?"Solicitud rechazada":e.getReason())); }
 @ExceptionHandler({IllegalArgumentException.class,MethodArgumentNotValidException.class,org.springframework.http.converter.HttpMessageNotReadableException.class}) ResponseEntity<?> invalid(Exception e) { return ResponseEntity.badRequest().body(Map.of("error","Datos inválidos")); }
 @ExceptionHandler(DataIntegrityViolationException.class) ResponseEntity<?> conflict(Exception e) { return ResponseEntity.status(409).body(Map.of("error","Conflicto de datos")); }
}
