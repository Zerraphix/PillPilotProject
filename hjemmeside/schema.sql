
BEGIN;

-- SLET EKSISTERENDE TABELLER
-- Slettes i omvendt rækkefølge af relationerne.

DROP TABLE IF EXISTS public.medicinudlevering;
DROP TABLE IF EXISTS public.udleveringsstatus;
DROP TABLE IF EXISTS public.medicinplan;
DROP TABLE IF EXISTS public.pilledispenser;
DROP TABLE IF EXISTS public.borger;
DROP TABLE IF EXISTS public.kontaktperson;



-- KONTAKTPERSON

CREATE TABLE public.kontaktperson (
    kontaktperson_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fornavn VARCHAR(100) NOT NULL,
    efternavn VARCHAR(100) NOT NULL,
    email VARCHAR(250) NOT NULL,
    password_hash TEXT NOT NULL,
    telefon VARCHAR(25),
    aktiv BOOLEAN NOT NULL DEFAULT TRUE,
    oprettet_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_kontaktperson_email
        UNIQUE (email)
);


-- BORGER

CREATE TABLE public.borger (
    borger_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kontaktperson_id INTEGER NOT NULL,
    fornavn VARCHAR(100) NOT NULL,
    efternavn VARCHAR(100) NOT NULL,
    birthday date NOT NULL,
    telefon VARCHAR(25),
    adresse TEXT,
    diagnose TEXT,
    allergi TEXT,
    aktiv BOOLEAN NOT NULL DEFAULT TRUE,
    oprettet_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_borger_kontaktperson
        FOREIGN KEY (kontaktperson_id)
        REFERENCES public.kontaktperson(kontaktperson_id)
        ON DELETE RESTRICT
);


-- PILLESDISPENSER

CREATE TABLE public.pilledispenser (
    pilledispenser_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borger_id INTEGER NOT NULL,
    enhed_id VARCHAR(100) NOT NULL,
    antal_rum INTEGER NOT NULL,
    drift_status VARCHAR(30) NOT NULL DEFAULT 'klar',
    seneste_set_at TIMESTAMPTZ,
    aktiv BOOLEAN NOT NULL DEFAULT TRUE,
    oprettet_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_pilledispenser_borger
        FOREIGN KEY (borger_id)
        REFERENCES public.borger(borger_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_pilledispenser_enhed
        UNIQUE (enhed_id),

    CONSTRAINT uq_pilledispenser_borger
        UNIQUE (borger_id),

    CONSTRAINT chk_pilledispenser_antal_rum
        CHECK (antal_rum > 0),

    CONSTRAINT chk_pilledispenser_drift_status
        CHECK (drift_status IN (
            'klar',
            'offline',
            'fejl',
            'vedligeholdelse'
        ))
);


-- MEDICINPLAN

CREATE TABLE public.medicinplan (
    medicinplan_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borger_id INTEGER NOT NULL,
    navn VARCHAR(100) NOT NULL,
    tidspunkt TIME NOT NULL,
    startdato DATE NOT NULL,
    slutdato DATE,
    aktiv BOOLEAN NOT NULL DEFAULT TRUE,
    oprettet_af INTEGER NOT NULL,
    oprettet_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_medicinplan_borger
        FOREIGN KEY (borger_id)
        REFERENCES public.borger(borger_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_medicinplan_kontaktperson
        FOREIGN KEY (oprettet_af)
        REFERENCES public.kontaktperson(kontaktperson_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_medicinplan_dato
        CHECK (slutdato IS NULL OR slutdato >= startdato)
);


-- UDLEVERINGSSTATUS

CREATE TABLE public.udleveringsstatus (
    status_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kode VARCHAR(30) NOT NULL,
    beskrivelse VARCHAR(255) NOT NULL,

    CONSTRAINT uq_udleveringsstatus_kode
        UNIQUE (kode)
);


-- MEDICINUDLEVERING

CREATE TABLE public.medicinudlevering (
    udlevering_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    medicinplan_id INTEGER NOT NULL,
    pilledispenser_id INTEGER NOT NULL,
    status_id INTEGER NOT NULL,
    planlagt_tid TIMESTAMPTZ NOT NULL,
    afhentningsfrist TIMESTAMPTZ NOT NULL,
    udleveret_tid TIMESTAMPTZ,
    afhentet_tid TIMESTAMPTZ,
    fejlbeskrivelse TEXT,
    oprettet_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_medicinudlevering_medicinplan
        FOREIGN KEY (medicinplan_id)
        REFERENCES public.medicinplan(medicinplan_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_medicinudlevering_pilledispenser
        FOREIGN KEY (pilledispenser_id)
        REFERENCES public.pilledispenser(pilledispenser_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_medicinudlevering_status
        FOREIGN KEY (status_id)
        REFERENCES public.udleveringsstatus(status_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_medicinudlevering_planlagt
        UNIQUE (medicinplan_id, planlagt_tid),

    CONSTRAINT chk_medicinudlevering_frist
        CHECK (afhentningsfrist >= planlagt_tid)
);


-- OPRET STANDARDSTATUSSER

INSERT INTO public.udleveringsstatus (kode, beskrivelse)
VALUES
    ('planlagt', 'Afventer planlagt udlevering'),
    ('udleveret', 'Medicinen er registreret udleveret'),
    ('ikke_afhentet', 'Medicinen er ikke afhentet inden fristen'),
    ('afhentet', 'Medicinen er registreret afhentet'),
    ('fejl', 'Der opstod en fejl under udlevering'),
    ('annulleret', 'Udleveringen blev annulleret');

COMMIT;
