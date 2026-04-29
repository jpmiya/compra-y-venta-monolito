package org.example.app.admin.repository;

import java.util.UUID;

import org.example.app.admin.domain.Person;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PersonRepository extends JpaRepository<Person, UUID> {

	boolean existsByDocumentIdHash(String documentIdHash);
}
