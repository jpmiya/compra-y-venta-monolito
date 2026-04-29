package org.example.app.admin.domain;

import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

@Entity
@Table(name = "person")
public class Person {

    @Id
    private UUID id;

    @Column(name = "full_name", nullable = false)
    private String fullName;

    @Column(name = "document_id_enc", nullable = false)
    private String documentIdEnc;

    @Column(name = "document_id_hash", nullable = false, unique = true, length = 64)
    private String documentIdHash;

    @Column(name = "phone_enc", nullable = false)
    private String phoneEnc;

    @Column(name = "registered_at", nullable = false)
    private Instant registeredAt;

    @Column(name = "birth_date", nullable = false)
    private LocalDate birthDate;

    @Column(nullable = false)
    private boolean active;

    @OneToMany(mappedBy = "person", fetch = FetchType.LAZY, cascade = CascadeType.ALL)
    private List<AppUser> users = new ArrayList<>();

    @PrePersist
    void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
        if (registeredAt == null) {
            registeredAt = Instant.now();
        }
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getFullName() {
        return fullName;
    }

    public void setFullName(String fullName) {
        this.fullName = fullName;
    }

    public String getDocumentIdEnc() {
        return documentIdEnc;
    }

    public void setDocumentIdEnc(String documentIdEnc) {
        this.documentIdEnc = documentIdEnc;
    }

    public String getDocumentIdHash() {
        return documentIdHash;
    }

    public void setDocumentIdHash(String documentIdHash) {
        this.documentIdHash = documentIdHash;
    }

    public String getPhoneEnc() {
        return phoneEnc;
    }

    public void setPhoneEnc(String phoneEnc) {
        this.phoneEnc = phoneEnc;
    }

    public Instant getRegisteredAt() {
        return registeredAt;
    }

    public void setRegisteredAt(Instant registeredAt) {
        this.registeredAt = registeredAt;
    }

    public LocalDate getBirthDate() {
        return birthDate;
    }

    public void setBirthDate(LocalDate birthDate) {
        this.birthDate = birthDate;
    }

    public boolean isActive() {
        return active;
    }

    public void setActive(boolean active) {
        this.active = active;
    }

    public List<AppUser> getUsers() {
        return users;
    }

    public void setUsers(List<AppUser> users) {
        this.users = users;
    }
}
