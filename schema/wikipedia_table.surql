USE NS test; USE DB test;

DEFINE TABLE wiki_embeddings SCHEMAFULL;

DEFINE FIELD url ON TABLE wiki_embeddings TYPE string
    ASSERT
        string::is::url($value);
DEFINE FIELD title ON TABLE wiki_embeddings TYPE string
    ASSERT
        string::len($value) > 0;
DEFINE FIELD text ON TABLE wiki_embeddings TYPE string
    ASSERT
        string::len($value) > 0;
DEFINE FIELD title_vector ON TABLE wiki_embeddings TYPE array<float>
    ASSERT
        array::len($value) = 1536;
DEFINE FIELD content_vector ON TABLE wiki_embeddings TYPE array<float>
    ASSERT
        array::len($value) = 1536;

DEFINE INDEX embeddings ON wiki_embeddings
    FIELDS content_vector
    MTREE DIMENSION 1536
    DIST COSINE;

