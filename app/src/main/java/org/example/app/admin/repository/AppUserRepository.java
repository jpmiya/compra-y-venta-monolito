package org.example.app.admin.repository;

import java.time.Instant;
import java.util.UUID;

import org.example.app.admin.domain.AppUser;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface AppUserRepository extends JpaRepository<AppUser, UUID> {

	boolean existsByEmail(String email);

	boolean existsByFirebaseUid(String firebaseUid);

	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("update AppUser u set u.lastAccessAt = :lastAccessAt where u.firebaseUid = :firebaseUid")
	int updateLastAccessByFirebaseUid(@Param("firebaseUid") String firebaseUid, @Param("lastAccessAt") Instant lastAccessAt);
}
