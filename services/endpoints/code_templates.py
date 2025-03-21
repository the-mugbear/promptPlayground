# services/endpoints/code_templates.py
CODE_TEMPLATES = {
    "giskard": """import os

    import os
    import requests
    from typing import Optional

    import litellm
    import giskard


    class MyCustomLLM(litellm.CustomLLM):
        def completion(self, messages: str, api_key: Optional[str] = None, **kwargs) -> litellm.ModelResponse:
            api_key = api_key or os.environ.get("MY_SECRET_KEY")
            if api_key is None:
                raise litellm.AuthenticationError("`api_key` was not provided")

            response = requests.post(
                "{{CHAT_ENDPOINT}}",
                json={"messages": messages},
                headers={"Authorization": api_key},
            )

            return litellm.ModelResponse(**response.json())

    os.eviron["MY_SECRET_KEY"] = "" # "my-secret-key"

    my_custom_llm = MyCustomLLM()
    litellm.custom_provider_map = [  # 👈 KEY STEP - REGISTER HANDLER
        {"provider": "my-custom-llm-endpoint", "custom_handler": my_custom_llm}
    ]
    giskard.llm.set_llm_model("my-custom-llm-endpoint/my-custom-model", api_key=api_key)""" }