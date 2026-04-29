package org.example.app.audit.repository;

import java.util.UUID;

import org.example.app.audit.domain.AuditLog;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AuditLogRepository extends JpaRepository<AuditLog, UUID> {
}
