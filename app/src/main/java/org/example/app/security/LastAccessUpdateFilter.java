package org.example.app.security;

import java.io.IOException;
import java.time.Instant;

import org.example.app.admin.repository.AppUserRepository;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Component
public class LastAccessUpdateFilter extends OncePerRequestFilter {

    private final AppUserRepository appUserRepository;

    public LastAccessUpdateFilter(AppUserRepository appUserRepository) {
        this.appUserRepository = appUserRepository;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof Jwt jwt) {
            String firebaseUid = jwt.getSubject();
            if (firebaseUid != null && !firebaseUid.isBlank()) {
                appUserRepository.updateLastAccessByFirebaseUid(firebaseUid, Instant.now());
            }
        }
        filterChain.doFilter(request, response);
    }
}
