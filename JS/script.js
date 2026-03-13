// 🌿 ECOFLUIDS - JS PERSONALIZADO
// -----------------------------------------------

// 1️⃣ Scroll suave nos links de navegação
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});


// 2️⃣ Envio do formulário de contacto com ligação ao PHP + MySQL
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('contactForm');

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const nome = document.getElementById('name').value.trim();
            const email = document.getElementById('email').value.trim();
            const mensagem = document.getElementById('message').value.trim();

            // Validações simples
            if (!nome || !email || !mensagem) {
                alert('⚠️ Por favor, preencha todos os campos antes de enviar.');
                return;
            }

            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                alert('📧 Por favor, introduza um email válido.');
                return;
            }

            try {
                // 🔗 Envia os dados para o PHP (AJAX via fetch)
                const response = await fetch('http://localhost/eco/api/salvar_mensagem.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nome, email, mensagem })
                });

                const data = await response.json();

                if (data.success) {
                    // Mostra o popup de sucesso
                    const successMsg = document.getElementById('successMessage');
                    successMsg.style.display = 'flex';
                    form.reset();

                    setTimeout(() => {
                        successMsg.style.display = 'none';
                    }, 4000);
                } else {
                    alert('❌ Erro ao enviar: ' + data.message);
                }
            } catch (error) {
                alert('⚠️ Não foi possível ligar ao servidor.');
            }
        });
    }
});


// 3️⃣ Fecha o popup ao clicar fora
document.getElementById('successMessage').addEventListener('click', function (e) {
    if (e.target === this) {
        this.style.display = 'none';
    }
});


document.getElementById('myInput').addEventListener('keyup', function() {
    let value = this.value.toLowerCase();
    let rows = document.querySelectorAll('#tableBody tr');
    
    rows.forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(value) ? '' : 'none';
    });
});

document.getElementById('inputPesquisa').addEventListener('keyup', function() {
    let busca = this.value.toLowerCase();
    let linhas = document.querySelectorAll('#tableBody tr');

    linhas.forEach(linha => {
        let texto = linha.innerText.toLowerCase();
        linha.style.display = texto.includes(busca) ? '' : 'none';
    });
});

function filtrarPorEstado() {
    let select = document.getElementById('filtroEstado');
    let valor = select.value;
    
    if (valor === "todos") {
        window.location.href = "{{ url_for('admin_pedidos') }}";
    } else if (valor === "pendente") {
        window.location.href = "{{ url_for('admin_pedidos') }}?estado=0";
    } else if (valor === "tratado") {
        window.location.href = "{{ url_for('admin_pedidos') }}?estado=1";
    }
}