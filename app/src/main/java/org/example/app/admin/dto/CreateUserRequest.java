package org.example.app.admin.dto;

import java.time.Instant;
import java.util.UUID;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record CreateUserRequest(
        @NotNull UUID personId,
        @NotBlank @Email String email,
        @NotBlank String firebaseUid,
        Instant lastAccessAt,
        Boolean active
) {
}
