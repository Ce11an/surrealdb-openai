DEFINE FUNCTION IF NOT EXISTS fn::embeddings_complete($embedding_model: string, $input: string) {
    RETURN http::post(
        "https://api.openai.com/v1/embeddings",
        {
            "model": $embedding_model,
            "input": $input
        },
        {
            "Authorization": fn::get_openai_token()
        }
    )["data"][0]["embedding"]
};

DEFINE FUNCTION IF NOT EXISTS fn::search_for_documents($input_vector: array<float>, $threshold: float) {
    LET $context =
     SELECT
        url,
        title,
        text
    FROM wiki_embeddings
    WHERE
        content_vector <|1|> $input_vector
            AND vector::similarity::cosine(content_vector, $input_vector) >= $threshold;

    RETURN IF !$context THEN
        ""
    ELSE
        type::string($context[0])
    END
};

DEFINE FUNCTION IF NOT EXISTS fn::get_prompt_with_context($context: string) {

    LET $prompt = "You are an AI assistant answering questions about anything from Simple English Wikipedia the context will provide you with the most relevant data from Simple English Wikipedia including the page title, url, and page content.

    If referencing the text/context refer to it as Simple English Wikipedia.

    At the end of the response, add one markdown link using the format: [Title](URL) and replace the title and url with the associated title and url of the more relevant page from the context.

    The maximum number of links you can include is 1, do not provide any other references or annotations.

    Only reply with the context provided. If the context is an empty string, reply with 'I am sorry, I do not know the answer.'.

    Do not use any prior knowledge that you have been trained on.

    <context>
        $context
    </context>";

    RETURN string::replace($prompt, '$context', $context);
};

DEFINE FUNCTION IF NOT EXISTS fn::chat_complete($llm: string, $question: string, $prompt_with_context: string) {
    RETURN http::post(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": $llm,
            "messages": [
                {
                 "role": "system",
                 "content": $prompt_with_context
                },
                {
                    "role": "user", "content": $question
                },
            ],
        "temperature": 0.5
    },
    {
        "Authorization": fn::get_openai_token()

    }
    )["choices"][0]["message"]["content"];
};

DEFINE FUNCTION IF NOT EXISTS fn::surreal_rag($llm: string, $input: string, $threshold: float) {

    LET $input_vector = fn::embeddings_complete("text-embedding-ada-002", $input);

    LET $context_document = fn::search_for_documents($input_vector, $threshold);

    LET $prompt_with_context = fn::get_prompt_with_context($context_document);

    RETURN fn::chat_complete($llm, $input, $prompt_with_context);
};

