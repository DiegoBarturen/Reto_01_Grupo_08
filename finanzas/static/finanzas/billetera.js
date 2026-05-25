document.addEventListener("DOMContentLoaded", () => {
    const montoInput = document.querySelector("#id_monto");
    const quickAmounts = document.querySelectorAll(".quick-amount");

    if (!montoInput || !quickAmounts.length) {
        return;
    }

    quickAmounts.forEach((button) => {
        button.addEventListener("click", () => {
            montoInput.value = button.dataset.amount;
            montoInput.focus();
        });
    });
});
