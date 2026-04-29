package org.example.app.audit.service;

import java.util.Map;

import org.example.app.audit.domain.AuditLog;
import org.example.app.audit.repository.AuditLogRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class AuditService {

    private static final Logger LOGGER = LoggerFactory.getLogger(AuditService.class);

    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;

    public AuditService(AuditLogRepository auditLogRepository, ObjectMapper objectMapper) {
        this.auditLogRepository = auditLogRepository;
        this.objectMapper = objectMapper;
    }

    public void log(String action, String entityName, String entityId, Map<String, Object> details) {
        AuditLog auditLog = new AuditLog();
        auditLog.setAction(action);
        auditLog.setEntityName(entityName);
        auditLog.setEntityId(entityId);
        auditLog.setActorUid(getActorUid());
        auditLog.setDetailsJson(writeAsJson(details));

        auditLogRepository.save(auditLog);
        LOGGER.info("AUDIT action={} entity={} entityId={} actorUid={}", action, entityName, entityId, auditLog.getActorUid());
    }

    private String getActorUid() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof Jwt jwt) {
            return jwt.getSubject();
        }
        return null;
    }

    private String writeAsJson(Map<String, Object> details) {
        if (details == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(details);
        } catch (JsonProcessingException exception) {
            return "{\"serializationError\":true}";
        }
    }
}
