package org.example.app.admin;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AdminControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
        @WithMockUser(roles = "ADMIN")
    void shouldCreateAndFetchPerson() throws Exception {
        String payload = objectMapper.writeValueAsString(new CreatePersonPayload(
                "Juan Perez",
                "DNI-12345678",
                "+5491122334455",
                LocalDate.of(1999, 1, 10),
                true
        ));

        MvcResult createResult = mockMvc.perform(post("/api/v1/admin/persons")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.fullName").value("Juan Perez"))
                .andReturn();

        JsonNode personJson = objectMapper.readTree(createResult.getResponse().getContentAsString());
        String personId = personJson.get("id").asText();

        mockMvc.perform(get("/api/v1/admin/persons/{personId}", personId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.documentId").value("DNI-12345678"));
    }

    @Test
        @WithMockUser(roles = "ADMIN")
    void shouldCreateUserForExistingPerson() throws Exception {
        String personPayload = objectMapper.writeValueAsString(new CreatePersonPayload(
                "Ana Gomez",
                "DNI-87654321",
                "+5491199988877",
                LocalDate.of(1995, 5, 20),
                true
        ));

        MvcResult personResult = mockMvc.perform(post("/api/v1/admin/persons")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(personPayload))
                .andExpect(status().isCreated())
                .andReturn();

        String personId = objectMapper.readTree(personResult.getResponse().getContentAsString()).get("id").asText();

        String userPayload = objectMapper.writeValueAsString(new CreateUserPayload(
                personId,
                "ana@example.com",
                "firebase-uid-001",
                true
        ));

        mockMvc.perform(post("/api/v1/admin/users")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(userPayload))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.email").value("ana@example.com"));

        mockMvc.perform(get("/api/v1/admin/users"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].firebaseUid").exists());

        MvcResult usersResult = mockMvc.perform(get("/api/v1/admin/users"))
                .andExpect(status().isOk())
                .andReturn();

        String userId = objectMapper.readTree(usersResult.getResponse().getContentAsString()).get(0).get("id").asText();

        mockMvc.perform(patch("/api/v1/admin/users/{userId}/deactivate", userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.active").value(false));
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    void shouldDeactivatePerson() throws Exception {
        String payload = objectMapper.writeValueAsString(new CreatePersonPayload(
                "Carlos Diaz",
                "DNI-00001111",
                "+5491100000000",
                LocalDate.of(1990, 3, 15),
                true
        ));

        MvcResult createResult = mockMvc.perform(post("/api/v1/admin/persons")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isCreated())
                .andReturn();

        String personId = objectMapper.readTree(createResult.getResponse().getContentAsString()).get("id").asText();

        mockMvc.perform(patch("/api/v1/admin/persons/{personId}/deactivate", personId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.active").value(false));
    }

        @Test
        @WithMockUser
        void shouldRejectNonAdminUser() throws Exception {
                mockMvc.perform(get("/api/v1/admin/persons"))
                                .andExpect(status().isForbidden());
        }

    private record CreatePersonPayload(
            String fullName,
            String documentId,
            String phone,
            LocalDate birthDate,
            Boolean active
    ) {
    }

    private record CreateUserPayload(
            String personId,
            String email,
            String firebaseUid,
            Boolean active
    ) {
    }
}
