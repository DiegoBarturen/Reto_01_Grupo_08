document.addEventListener("DOMContentLoaded", () => {
    const guide = document.querySelector("[data-password-guide]");
    const passwordInput = document.querySelector("#id_password1");

    if (!guide || !passwordInput) {
        return;
    }

    const usernameInput = document.querySelector("#id_username");
    const firstNameInput = document.querySelector("#id_first_name");
    const lastNameInput = document.querySelector("#id_last_name");
    const emailInput = document.querySelector("#id_email");
    const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
    const validateUrl = guide.dataset.validateUrl;
    const ruleItems = new Map(
        Array.from(guide.querySelectorAll("[data-rule]")).map((item) => [item.dataset.rule, item]),
    );

    let timeoutId = null;

    const setRuleState = (rule, isValid) => {
        const item = ruleItems.get(rule);
        if (!item) {
            return;
        }
        item.classList.toggle("is-valid", Boolean(isValid));
    };

    const updateGuide = (results) => {
        if (!results.has_password) {
            ruleItems.forEach((item) => item.classList.remove("is-valid"));
            return;
        }
        Object.entries(results).forEach(([rule, isValid]) => setRuleState(rule, isValid));
    };

    const requestValidation = async () => {
        const payload = new URLSearchParams({
            username: usernameInput?.value ?? "",
            first_name: firstNameInput?.value ?? "",
            last_name: lastNameInput?.value ?? "",
            email: emailInput?.value ?? "",
            password: passwordInput.value,
        });

        try {
            const response = await fetch(validateUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-CSRFToken": csrfInput?.value ?? "",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: payload.toString(),
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();
            updateGuide(data);
        } catch (error) {
            console.error("No se pudo validar la contrasena en vivo.", error);
        }
    };

    const queueValidation = () => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(requestValidation, 180);
    };

    [passwordInput, usernameInput, firstNameInput, lastNameInput, emailInput].forEach((input) => {
        input?.addEventListener("input", queueValidation);
    });
});
