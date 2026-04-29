package org.example.app.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class CryptoService {

    private static final String ALGORITHM = "AES";
    private static final String CIPHER_TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int TAG_LENGTH_BITS = 128;
    private static final int IV_LENGTH_BYTES = 12;

    private final SecretKeySpec secretKeySpec;
    private final String hashSalt;
    private final SecureRandom secureRandom = new SecureRandom();

    public CryptoService(
            @Value("${app.crypto.master-key-base64}") String masterKeyBase64,
            @Value("${app.crypto.hash-salt}") String hashSalt
    ) {
        byte[] keyBytes = Base64.getDecoder().decode(masterKeyBase64);
        if (keyBytes.length != 16 && keyBytes.length != 24 && keyBytes.length != 32) {
            throw new IllegalStateException("Invalid AES key length. Use 128, 192, or 256-bit base64 key");
        }
        this.secretKeySpec = new SecretKeySpec(keyBytes, ALGORITHM);
        this.hashSalt = hashSalt;
    }

    public String encrypt(String plainText) {
        if (plainText == null) {
            return null;
        }
        try {
            byte[] iv = new byte[IV_LENGTH_BYTES];
            secureRandom.nextBytes(iv);

            Cipher cipher = Cipher.getInstance(CIPHER_TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, secretKeySpec, new GCMParameterSpec(TAG_LENGTH_BITS, iv));
            byte[] encrypted = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));

            byte[] result = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, result, 0, iv.length);
            System.arraycopy(encrypted, 0, result, iv.length, encrypted.length);

            return Base64.getEncoder().encodeToString(result);
        } catch (Exception exception) {
            throw new IllegalStateException("Could not encrypt data", exception);
        }
    }

    public String decrypt(String encryptedText) {
        if (encryptedText == null) {
            return null;
        }
        try {
            byte[] decoded = Base64.getDecoder().decode(encryptedText);
            byte[] iv = new byte[IV_LENGTH_BYTES];
            byte[] encrypted = new byte[decoded.length - IV_LENGTH_BYTES];

            System.arraycopy(decoded, 0, iv, 0, iv.length);
            System.arraycopy(decoded, iv.length, encrypted, 0, encrypted.length);

            Cipher cipher = Cipher.getInstance(CIPHER_TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, secretKeySpec, new GCMParameterSpec(TAG_LENGTH_BITS, iv));
            byte[] plain = cipher.doFinal(encrypted);
            return new String(plain, StandardCharsets.UTF_8);
        } catch (Exception exception) {
            throw new IllegalStateException("Could not decrypt data", exception);
        }
    }

    public String hash(String value) {
        if (value == null) {
            return null;
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashBytes = digest.digest((hashSalt + ":" + value).getBytes(StandardCharsets.UTF_8));
            StringBuilder hash = new StringBuilder();
            for (byte hashByte : hashBytes) {
                hash.append(String.format("%02x", hashByte));
            }
            return hash.toString();
        } catch (Exception exception) {
            throw new IllegalStateException("Could not hash data", exception);
        }
    }
}
