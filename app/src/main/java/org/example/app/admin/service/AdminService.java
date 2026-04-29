package org.example.app.admin.service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.example.app.admin.domain.AppUser;
import org.example.app.admin.domain.Person;
import org.example.app.admin.dto.CreatePersonRequest;
import org.example.app.admin.dto.CreateUserRequest;
import org.example.app.admin.dto.PersonResponse;
import org.example.app.admin.dto.UserResponse;
import org.example.app.admin.repository.AppUserRepository;
import org.example.app.admin.repository.PersonRepository;
import org.example.app.audit.service.AuditService;
import org.example.app.security.CryptoService;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
@Transactional
public class AdminService {

    private final PersonRepository personRepository;
    private final AppUserRepository appUserRepository;
    private final CryptoService cryptoService;
    private final AuditService auditService;

    public AdminService(
            PersonRepository personRepository,
            AppUserRepository appUserRepository,
            CryptoService cryptoService,
            AuditService auditService
    ) {
        this.personRepository = personRepository;
        this.appUserRepository = appUserRepository;
        this.cryptoService = cryptoService;
        this.auditService = auditService;
    }

    public PersonResponse createPerson(CreatePersonRequest request) {
        String documentIdHash = cryptoService.hash(request.documentId());
        if (personRepository.existsByDocumentIdHash(documentIdHash)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Person document already exists");
        }

        Person person = new Person();
        person.setFullName(request.fullName());
        person.setDocumentIdHash(documentIdHash);
        person.setDocumentIdEnc(cryptoService.encrypt(request.documentId()));
        person.setPhoneEnc(cryptoService.encrypt(request.phone()));
        person.setBirthDate(request.birthDate());
        person.setActive(request.active() == null || request.active());

        try {
            Person saved = personRepository.save(person);
            auditService.log("PERSON_CREATED", "Person", saved.getId().toString(), details("fullName", saved.getFullName()));
            return toPersonResponse(saved);
        } catch (DataIntegrityViolationException exception) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Person document already exists");
        }
    }

    @Transactional(readOnly = true)
    public List<PersonResponse> listPeople() {
        return personRepository.findAll().stream().map(this::toPersonResponse).toList();
    }

    @Transactional(readOnly = true)
    public PersonResponse getPerson(UUID personId) {
        Person person = findPersonOrThrow(personId);
        return toPersonResponse(person);
    }

    public PersonResponse deactivatePerson(UUID personId) {
        Person person = findPersonOrThrow(personId);
        person.setActive(false);
        person.getUsers().forEach(user -> user.setActive(false));
        auditService.log("PERSON_DEACTIVATED", "Person", personId.toString(), null);
        return toPersonResponse(person);
    }

    public UserResponse createUser(CreateUserRequest request) {
        Person person = findPersonOrThrow(request.personId());

        if (appUserRepository.existsByEmail(request.email())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "User email already exists");
        }
        if (appUserRepository.existsByFirebaseUid(request.firebaseUid())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Firebase UID already exists");
        }

        AppUser user = new AppUser();
        user.setPerson(person);
        user.setEmail(request.email());
        user.setFirebaseUid(request.firebaseUid());
        user.setLastAccessAt(request.lastAccessAt());
        user.setActive(request.active() == null || request.active());

        try {
            AppUser saved = appUserRepository.save(user);
            auditService.log("USER_CREATED", "AppUser", saved.getId().toString(), details("personId", person.getId()));
            return toUserResponse(saved);
        } catch (DataIntegrityViolationException exception) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "User email or firebase UID already exists");
        }
    }

    @Transactional(readOnly = true)
    public List<UserResponse> listUsers() {
        return appUserRepository.findAll().stream().map(this::toUserResponse).toList();
    }

    public UserResponse deactivateUser(UUID userId) {
        AppUser user = findUserOrThrow(userId);
        user.setActive(false);
        auditService.log("USER_DEACTIVATED", "AppUser", userId.toString(), null);
        return toUserResponse(user);
    }

    private Person findPersonOrThrow(UUID personId) {
        return personRepository.findById(personId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Person not found"));
    }

    private PersonResponse toPersonResponse(Person person) {
        return new PersonResponse(
                person.getId(),
                person.getFullName(),
                cryptoService.decrypt(person.getDocumentIdEnc()),
                cryptoService.decrypt(person.getPhoneEnc()),
                person.getRegisteredAt(),
                person.getBirthDate(),
                person.isActive()
        );
    }

    private AppUser findUserOrThrow(UUID userId) {
        return appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));
    }

    private Map<String, Object> details(String key, Object value) {
        Map<String, Object> details = new HashMap<>();
        details.put(key, value);
        return details;
    }

    private UserResponse toUserResponse(AppUser user) {
        return new UserResponse(
                user.getId(),
                user.getPerson().getId(),
                user.getEmail(),
                user.getFirebaseUid(),
                user.getLastAccessAt(),
                user.isActive()
        );
    }
}
