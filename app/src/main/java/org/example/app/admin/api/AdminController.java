package org.example.app.admin.api;

import java.util.List;
import java.util.UUID;

import org.example.app.admin.dto.CreatePersonRequest;
import org.example.app.admin.dto.CreateUserRequest;
import org.example.app.admin.dto.PersonResponse;
import org.example.app.admin.dto.UserResponse;
import org.example.app.admin.service.AdminService;
import org.springframework.http.HttpStatus;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin")
@Validated
public class AdminController {

    private final AdminService adminService;

    public AdminController(AdminService adminService) {
        this.adminService = adminService;
    }

    @PostMapping("/persons")
    @ResponseStatus(HttpStatus.CREATED)
    public PersonResponse createPerson(@RequestBody @Valid CreatePersonRequest request) {
        return adminService.createPerson(request);
    }

    @GetMapping("/persons")
    public List<PersonResponse> listPeople() {
        return adminService.listPeople();
    }

    @GetMapping("/persons/{personId}")
    public PersonResponse getPerson(@PathVariable UUID personId) {
        return adminService.getPerson(personId);
    }

    @PatchMapping("/persons/{personId}/deactivate")
    public PersonResponse deactivatePerson(@PathVariable UUID personId) {
        return adminService.deactivatePerson(personId);
    }

    @PostMapping("/users")
    @ResponseStatus(HttpStatus.CREATED)
    public UserResponse createUser(@RequestBody @Valid CreateUserRequest request) {
        return adminService.createUser(request);
    }

    @GetMapping("/users")
    public List<UserResponse> listUsers() {
        return adminService.listUsers();
    }

    @PatchMapping("/users/{userId}/deactivate")
    public UserResponse deactivateUser(@PathVariable UUID userId) {
        return adminService.deactivateUser(userId);
    }
}
