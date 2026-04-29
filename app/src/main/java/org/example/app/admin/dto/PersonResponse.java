package org.example.app.admin.dto;

import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public record PersonResponse(
        UUID id,
        String fullName,
        String documentId,
        String phone,
        Instant registeredAt,
        LocalDate birthDate,
        boolean active
) {
}
