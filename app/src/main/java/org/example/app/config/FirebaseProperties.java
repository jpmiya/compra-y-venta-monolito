package org.example.app.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.firebase")
public record FirebaseProperties(
        String projectId,
        String issuerUri,
        String jwkSetUri
) {
}
