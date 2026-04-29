package org.example.app.admin.dto;

import java.time.Instant;
import java.util.UUID;

public record UserResponse(
        UUID id,
        UUID personId,
        String email,
        String firebaseUid,
        Instant lastAccessAt,
        boolean active
) {
}
