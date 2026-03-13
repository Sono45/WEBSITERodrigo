document.addEventListener("DOMContentLoaded", () => {
    const dropdownItems = document.querySelectorAll(".lang-option");
    const currentFlag = document.getElementById("currentFlag");
    const currentLangLabel = document.getElementById("currentLangLabel");
    const langFilePath = "/json/lang.json";

    // Idioma padrão ou guardado no localStorage
    let currentLang = localStorage.getItem("lang") || "pt";

    // Função para aplicar as traduções
    function applyTranslations(langData) {
        document.querySelectorAll("[data-key]").forEach(el => {
            const key = el.getAttribute("data-key");
            const text = key.split('.').reduce((obj, k) => (obj || {})[k], langData);
            if (text) el.textContent = text; // mais seguro que innerHTML
        });
    }

    // Função para carregar as traduções
    async function loadLanguage(lang) {
        try {
            const res = await fetch(langFilePath);
            if (!res.ok) throw new Error("Erro ao carregar JSON");
            const data = await res.json();

            console.log("Idioma carregado:", lang);
            console.log("Conteúdo JSON:", data);

            if (data[lang]) {
                applyTranslations(data[lang]);
                localStorage.setItem("lang", lang);
                currentLang = lang;
                updateDropdown(lang);
            } else {
                console.warn(`Idioma '${lang}' não encontrado no JSON.`);
            }
        } catch (err) {
            console.error("Erro ao aplicar idioma:", err);
        }
    }

    // Atualiza a flag e o rótulo no menu
    function updateDropdown(lang) {
        const flagMap = {
            pt: "/flags/pt.png",
            en: "/flags/gb-eng.png",
            es: "/flags/es.png",
            fr: "/flags/fr.png",
            de: "/flags/de.png",
            it: "/flags/it.png"
        };

        const labelMap = {
            pt: "PT",
            en: "EN",
            es: "ES",
            fr: "FR",
            de: "DE",
            it: "IT"
        };

        if (currentFlag) currentFlag.src = flagMap[lang];
        if (currentLangLabel) currentLangLabel.textContent = labelMap[lang];
    }

    // Evento ao clicar em idioma
    dropdownItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const lang = item.getAttribute("data-lang");
            loadLanguage(lang);
        });
    });

    // Ao carregar a página
    loadLanguage(currentLang);
});
