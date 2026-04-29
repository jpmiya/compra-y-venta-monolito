package org.example.app.admin.dto;

import java.time.LocalDate;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record CreatePersonRequest(
        @NotBlank String fullName,
        @NotBlank String documentId,
        @NotBlank String phone,
        @NotNull LocalDate birthDate,
        Boolean active
) {
}
