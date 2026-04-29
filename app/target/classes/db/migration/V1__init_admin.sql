CREATE TABLE person (
    id UUID PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    document_id VARCHAR(50) NOT NULL UNIQUE,
    phone VARCHAR(50) NOT NULL,
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    birth_date DATE NOT NULL,
    active BOOLEAN NOT NULL
);

CREATE TABLE app_user (
    id UUID PRIMARY KEY,
    person_id UUID NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    firebase_uid VARCHAR(150) NOT NULL UNIQUE,
    last_access_at TIMESTAMP WITH TIME ZONE,
    active BOOLEAN NOT NULL,
    CONSTRAINT fk_app_user_person
        FOREIGN KEY (person_id) REFERENCES person (id)
);
