ALTER TABLE person
    ADD COLUMN document_id_enc TEXT,
    ADD COLUMN document_id_hash VARCHAR(64),
    ADD COLUMN phone_enc TEXT;

UPDATE person
SET document_id_enc = document_id,
    phone_enc = phone,
    document_id_hash = md5(document_id)
WHERE document_id_enc IS NULL OR phone_enc IS NULL OR document_id_hash IS NULL;

ALTER TABLE person
    ALTER COLUMN document_id_enc SET NOT NULL,
    ALTER COLUMN phone_enc SET NOT NULL,
    ALTER COLUMN document_id_hash SET NOT NULL;

ALTER TABLE person
    ADD CONSTRAINT uk_person_document_id_hash UNIQUE (document_id_hash);

ALTER TABLE person DROP COLUMN document_id;
ALTER TABLE person DROP COLUMN phone;

CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    actor_uid VARCHAR(150),
    action VARCHAR(80) NOT NULL,
    entity_name VARCHAR(80) NOT NULL,
    entity_id VARCHAR(80),
    details_json TEXT
);
