/* ===========================
   CONFIGURAÇÃO
=========================== */
const API_BASE_URL = "http://127.0.0.1:5000";
const TOKEN_KEY = "authToken";
const THEME_KEY = "themePreference"; // NOVA CHAVE
const CHAT_POLL_MS = 2000;

let _chatPollTimer = null;
let _glicemiaChart = null; // Adicionado para gerenciar o Chart (necessário para a próxima iteração)


/* ===========================
   FUNÇÕES ÚTEIS
=========================== */
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}
function setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
}

/**
 * CORREÇÃO DE HORÁRIO: Analisa a string de data, tratando 
 * strings de input 'datetime-local' (YYYY-MM-DDTHH:MM) como local time, 
 * e strings ISO (UTC) como datas que precisam de conversão normal.
 */
function formatTimestamp(isoString) {
    if (!isoString) return '';

    try {
        let date;
        
        // Se a string for do formato 'YYYY-MM-DDTHH:MM' (vindo do input datetime-local),
        // a tratamos como horário local para evitar o erro de fuso horário.
        if (isoString.includes('T') && isoString.length >= 16 && isoString.length <= 19 && !isoString.endsWith('Z')) {
            const [datePart, timePart] = isoString.split('T');
            const [year, month, day] = datePart.split('-').map(Number);
            const [hour, minute] = timePart.split(':').map(Number);
            
            // Cria um objeto Date com a hora local (mês é 0-indexado)
            date = new Date(year, month - 1, day, hour, minute); 
            
        } else {
            // Para timestamps principais (gerados pelo Python em UTC), 
            // a conversão new Date() + toLocaleString() funciona corretamente.
            date = new Date(isoString);
        }

        // Formata para o horário local (do navegador)
        return date.toLocaleDateString('pt-BR') + ' ' + date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        console.warn("Erro ao analisar timestamp:", e);
        return isoString; 
    }
}

async function apiFetch(endpoint, method = "GET", body = null) {
    const headers = {};
    if (!(body instanceof FormData)) headers["Content-Type"] = "application/json";

    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const options = { method, headers };
    if (body) options.body = (body instanceof FormData) ? body : JSON.stringify(body);

    try {
        const res = await fetch(API_BASE_URL + endpoint, options);
        const text = await res.text().catch(()=>null);
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch(e) { data = text; }
        return { ok: res.ok, status: res.status, data, resp: res };
    } catch (err) {
        console.error("apiFetch error:", err);
        return { ok: false, status: 0, data: null, error: err };
    }
}

/* ===========================
   TEMA ESCURO (DARK MODE) - NOVO BLOCO
=========================== */
function applyTheme(theme) {
    document.body.classList.toggle('dark', theme === 'dark');
    // Atualiza texto e estado do checkbox no menu
    const icon = document.getElementById('temaIcon');
    const label = document.getElementById('temaLabel');
    const checkbox = document.getElementById('temaCheckbox');

    if (icon) icon.textContent = theme === 'dark' ? '🌕' : '🌓';
    if (label) label.textContent = theme === 'dark' ? 'Modo Claro' : 'Modo Escuro';
    if (checkbox) checkbox.checked = theme === 'dark';
}

function loadTheme() {
    const savedTheme = localStorage.getItem(THEME_KEY);
    if (savedTheme) {
        applyTheme(savedTheme);
        return;
    }

    // Se não salvou, checa a preferência do sistema
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        applyTheme('dark');
    } else {
        applyTheme('light');
    }
}

function saveTheme(theme) {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    // Destrói e recria o gráfico se estiver na tela de histórico para aplicar o novo tema
    if (window.location.pathname.endsWith('historico.html')) {
        carregarHistorico();
    }
}

function toggleTheme() {
    const currentTheme = document.body.classList.contains('dark') ? 'dark' : 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    saveTheme(newTheme);
}
/* ===========================
   Botão de Login (REMOVIDO: Lógica antiga do #authButton)
=========================== */

/* ===========================
   AUTENTICAÇÃO
=========================== */
async function registrar() {
    const email = document.getElementById("cadastroEmail")?.value;
    const senha = document.getElementById("cadastroSenha")?.value;

    if (!email || !senha) {
        alert("Preencha email e senha!");
        return;
    }

    const res = await apiFetch("/api/register", "POST", { email, password: senha });

    if (res.ok) {
        alert("Conta criada com sucesso!");
        window.location.href = "login.html";
    } else {
        alert(res.data?.message || "Erro ao registrar.");
    }
}

async function login() {
    const email = document.getElementById("loginEmail")?.value;
    const senha = document.getElementById("loginSenha")?.value;

    if (!email || !senha) {
        alert("Informe email e senha!");
        return;
    }

    const res = await apiFetch("/api/login", "POST", { email, password: senha });

    if (res.ok && res.data?.token) {
        setToken(res.data.token);
        alert("Login realizado!");
        // Redireciona para o index após o login
        window.location.href = "index.html";
    } else {
        alert(res.data?.message || "Erro ao fazer login.");
    }
}

function logout() {
    setToken(null);
    alert("Você saiu da conta.");
    window.location.href = "login.html";
}

/* ===========================
   REGISTRO DE GLICEMIA
=========================== */
async function salvarRegistro() {
    const valorEl = document.getElementById("valorGlicemia");
    const valor = valorEl ? parseFloat(String(valorEl.value).replace(',', '.')) : NaN;
    const ultimaRefeicao = document.getElementById("ultimaRefeicao")?.value || "";
    const ultimoExercicio = document.getElementById("ultimoExercicio")?.value || "";
    const sintomas = document.getElementById("sintomas")?.value || "";

    if (isNaN(valor) || valor < 0) {
        alert("Valor de glicemia inválido!");
        return;
    }

    const payload = {
        valorGlicemia: valor,
        ultimaRefeicao,
        ultimoExercicio,
        sintomas
    };

    const res = await apiFetch("/api/record", "POST", payload);

    if (res.ok) {
        alert("Registro salvo com sucesso!");
        if (document.getElementById("registroForm")) document.getElementById("registroForm").reset();
        // refresh history if on that page
        if (document.getElementById("historicoBody")) carregarHistorico();
    } else {
        alert(res.data?.message || "Erro ao salvar.");
    }
}

/* ===========================
   HISTÓRICO + GRÁFICO
=========================== */
async function carregarHistorico() {
    const tabela = document.getElementById("historicoBody");
    const grafico = document.getElementById("graficoGlicemia");

    const res = await apiFetch("/api/records");
    if (!res.ok || !Array.isArray(res.data)) {
        if (tabela) tabela.innerHTML = "<tr><td colspan='5'>Nenhum registro.</td></tr>";
        if (_glicemiaChart) { _glicemiaChart.destroy(); _glicemiaChart = null; }
        return;
    }

    const registros = res.data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)); // Mais recente primeiro para tabela

    if (tabela) {
        tabela.innerHTML = registros.map(r => `
            <tr>
                <td>${formatTimestamp(r.timestamp)}</td>
                <td>${r.value}</td>
                <td>${r.meal_time ? formatTimestamp(r.meal_time) : "—"}</td>
                <td>${r.exercise_time ? formatTimestamp(r.exercise_time) : "—"}</td>
                <td>${r.symptoms || "—"}</td>
            </tr>
        `).join("");
    }
    
    // Preparação para Gráfico (ordem cronológica: mais antigo primeiro)
    const chartData = res.data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const labels = chartData.map(r => formatTimestamp(r.timestamp));
    const valores = chartData.map(r => r.value);
    
    // Configurações do gráfico
    const isDark = document.body.classList.contains('dark');
    const chartColor = isDark ? '#57d084' : '#4caf50';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const tickColor = isDark ? '#e6eef8' : '#111827';


    if (grafico && typeof Chart !== "undefined") {
        
        // Destrói a instância anterior do gráfico (CORREÇÃO)
        if (_glicemiaChart) {
             _glicemiaChart.destroy();
             _glicemiaChart = null;
        }

        try {
            _glicemiaChart = new Chart(grafico.getContext("2d"), {
                type: "line",
                data: {
                    labels,
                    datasets: [{
                        label: "Glicemia (mg/dL)",
                        data: valores,
                        borderColor: chartColor,
                        backgroundColor: chartColor.replace('1)', '0.1)'),
                        borderWidth: 3,
                        tension: 0.4,
                        pointRadius: 5
                    }]
                },
                options: { 
                    responsive: true, 
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: false,
                            grid: { color: gridColor },
                            ticks: { color: tickColor }
                        },
                        x: {
                            grid: { color: gridColor },
                            ticks: { color: tickColor }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: {
                                color: tickColor
                            }
                        }
                    }
                }
            });
        } catch (err) {
            console.warn("Erro ao desenhar gráfico:", err);
        }
    }
}

/* ===========================
   ANÁLISE (opcional)
=========================== */
async function carregarAnalise() {
    const el = document.getElementById("analysis-message");
    if (!el) return;

    const res = await apiFetch("/api/analyze");

    if (res.ok && res.data?.message) {
        el.textContent = res.data.message;
    } else {
        el.textContent = "Sem análise disponível.";
    }
}

/* ===========================
   CHAT PÚBLICO
=========================== */
async function carregarChat() {
    const box = document.getElementById("chatBox");
    if (!box) return;

    const res = await apiFetch("/api/chat/messages");
    if (!res.ok) return;

    box.innerHTML = res.data.map(m => `
        <div class="msg">
            <strong>${escapeHtml(m.username)}</strong>
            <small>${formatTimestamp(m.timestamp)}</small>
            <p>${escapeHtml(m.content)}</p>
        </div>
    `).join("");

    box.scrollTop = box.scrollHeight;
}

async function enviarMensagem() {
    const input = document.getElementById("chatInput");
    const msg = input ? input.value : '';
    if (!msg || !msg.trim()) return;

    const res = await apiFetch("/api/chat/messages", "POST", { content: msg.trim() });
    if (!res.ok) {
        alert(res.data?.message || "Erro ao enviar mensagem");
        return;
    }

    if (input) input.value = "";
    await carregarChat();
}

function startChatPolling() {
    if (_chatPollTimer) clearInterval(_chatPollTimer);
    // initial load
    carregarChat();
    _chatPollTimer = setInterval(carregarChat, CHAT_POLL_MS);
}

function stopChatPolling() {
    if (_chatPollTimer) {
        clearInterval(_chatPollTimer);
        _chatPollTimer = null;
    }
}

/* ---------------------------
   EMERGENCY - frontend
   --------------------------- */
async function sendEmergencyRequest(includeLastReport = true) {
  // chama o backend para disparar os Telegrams
  const payload = { include_last_report: !!includeLastReport };
  const res = await apiFetch('/api/emergency', 'POST', payload);
  return res;
}

function setupEmergencyUI() {
  const btn = document.getElementById('emergencyBtn');
  const statusEl = document.getElementById('emergencyStatus');
  const chk = document.getElementById('includeLastReport');

  if (!btn) return; // nada a fazer se botão não existir

  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!confirm('Tem certeza que deseja enviar um alerta de emergência agora?')) return;

    btn.disabled = true;
    if (statusEl) {
        statusEl.style.color = '#333';
        statusEl.textContent = 'Enviando alerta...';
    }

    const include = chk ? chk.checked : true;
    const res = await sendEmergencyRequest(include);

    if (res.ok) {
      if (statusEl) {
        statusEl.style.color = 'green';
        statusEl.textContent = 'Alerta enviado com sucesso!';
      }
    } else {
      if (statusEl) {
        statusEl.style.color = 'red';
        const msg = res.data?.message || `Erro ao enviar alerta (status ${res.status})`;
        statusEl.textContent = msg;
      }
    }

    // pequeno cooldown para evitar spam
    setTimeout(() => { btn.disabled = false; }, 5000);
  });
}


/* ===========================
   HELPERS UI
=========================== */
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
}

/* ===========================
   INICIALIZAÇÃO POR PÁGINA
=========================== */
document.addEventListener("DOMContentLoaded", () => {
    // Carrega o tema (Dark/Light Mode) no início
    loadTheme();

    // Setup Emergency UI (chamado aqui para garantir que o DOM esteja pronto)
    if (document.getElementById('emergencyBtn')) setupEmergencyUI();

    // Cadastro
    const btnCad = document.getElementById("btnCadastro");
    if (btnCad) btnCad.onclick = (e) => { e.preventDefault(); registrar(); };

    // Login
    const btnLog = document.getElementById("btnLogin");
    if (btnLog) btnLog.onclick = (e) => { e.preventDefault(); login(); };

    // Logout (referente aos botões no login/cadastro)
    // A lógica de logout principal está no Menu de Usuário
    const btnLogout = document.getElementById("logoutBtn");
    if (btnLogout) btnLogout.onclick = (e) => { e.preventDefault(); logout(); };

    // Registro de glicemia (salvar)
    const btnSalvar = document.getElementById("btnSalvar");
    if (btnSalvar) btnSalvar.onclick = (e) => { e.preventDefault(); salvarRegistro(); };

    // Histórico
    if (document.getElementById("historicoBody")) carregarHistorico();

    // Análise
    carregarAnalise();

    // Chat
    const chatSendBtn = document.getElementById("chatSendBtn") || document.getElementById("chatSend");
    if (chatSendBtn) {
        chatSendBtn.onclick = (e) => { e.preventDefault(); enviarMensagem(); };
    }
    if (document.getElementById("chatBox")) startChatPolling();
});

/* ===========================
   MENU DE USUÁRIO E MODAIS
=========================== */
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('userMenuBtn');
  const menu = document.getElementById('userMenuDropdown');

  // Toggle menu
  if (btn) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.toggle('active');
      btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      menu.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    });
  }

  // Close when click outside
  document.addEventListener('click', (e) => {
    if (!menu) return;
    if (btn && !menu.contains(e.target) && !btn.contains(e.target)) {
      menu.classList.remove('active');
      menu.setAttribute('aria-hidden', 'true');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    }
  });

  // Helpers: modal open/close
  function openModal(id) {
    const m = document.getElementById(id);
    if (!m) return;
    m.classList.add('show');
    m.setAttribute('aria-hidden', 'false');
  }
  function closeModal(id) {
    const m = document.getElementById(id);
    if (!m) return;
    m.classList.remove('show');
    m.setAttribute('aria-hidden', 'true');
  }

  // wire modal close buttons
  document.querySelectorAll('.modal-close, [data-target]').forEach(el => {
    el.addEventListener('click', (ev) => {
      ev.preventDefault();
      const t = el.getAttribute('data-target');
      if (t) closeModal(t);
      else {
        // if close button inside header has no data-target, climb to parent modal
        const parentModal = el.closest('.modal');
        if (parentModal) closeModal(parentModal.id);
      }
    });
  });

  // Pre-fill user info via API (requires /api/user/me)
  async function fillUserInfo() {
    try {
      const res = await apiFetch('/api/user/me', 'GET');
      if (!res.ok) {
        // Se não houver token ou erro: redireciona para login
        if (getToken()) {
            console.error("Token exists, but /api/user/me failed. Setting default user info.");
        } else {
            // Se não está logado, redireciona o usuário para fazer login
             if (!window.location.pathname.endsWith('/login.html') && !window.location.pathname.endsWith('/cadastro.html')) {
                 window.location.href = "login.html";
                 return;
             }
             return;
        }

        const fallback = localStorage.getItem('userEmail') || 'Usuário';
        const display = fallback.split('@')[0] || fallback;
        if (document.getElementById('umdName')) document.getElementById('umdName').textContent = display;
        if (document.getElementById('umdUsername')) document.getElementById('umdUsername').textContent = '@' + (display.replace(/\s+/g,'').toLowerCase() || 'user');
        if (document.getElementById('userMenuName')) document.getElementById('userMenuName').textContent = display;
        return;
      }
      
      const data = res.data || {};
      const email = data.email || localStorage.getItem('userEmail') || 'Usuário';
      const display = email.split('@')[0] || email;
      
      // Atualiza labels do menu
      const username = data.username || display.replace(/\s+/g,'').toLowerCase();
      if (document.getElementById('umdName')) document.getElementById('umdName').textContent = display;
      if (document.getElementById('umdUsername')) document.getElementById('umdUsername').textContent = '@' + username;
      if (document.getElementById('userMenuName')) document.getElementById('userMenuName').textContent = display;
      
      // modal values
      const modalEmail = document.getElementById('modalEmail');
      const modalChat = document.getElementById('modalTelegramChat');
      const modalTrust = document.getElementById('modalTrustedChat');
      if (modalEmail) modalEmail.value = data.email || '';
      if (modalChat) modalChat.value = data.telegram_chat_id || '';
      if (modalTrust) modalTrust.value = data.trusted_telegram_id || '';
      if (data.email) localStorage.setItem('userEmail', data.email);
    } catch (err) {
      console.error('Erro ao carregar /api/user/me', err);
      // Redireciona para login se houver erro grave na tentativa de carregar info
      if (!getToken()) {
        if (!window.location.pathname.endsWith('/login.html') && !window.location.pathname.endsWith('/cadastro.html')) {
             window.location.href = "login.html";
        }
      }
    }
  }

  // Menu item handlers
  const atualizar = document.getElementById('menuAtualizarDados');
  const configuracoes = document.getElementById('menuConfiguracoes');
  const ajuda = document.getElementById('menuAjuda');
  const logoutItem = document.getElementById('menuLogout');
  const themeCheckbox = document.getElementById('temaCheckbox'); // Novo

  if (atualizar) atualizar.addEventListener('click', () => { openModal('modalUpdate'); if(menu) menu.classList.remove('active'); });
  if (configuracoes) configuracoes.addEventListener('click', () => { openModal('modalConfig'); if(menu) menu.classList.remove('active'); });
  if (ajuda) ajuda.addEventListener('click', () => { openModal('modalHelp'); if(menu) menu.classList.remove('active'); });

  // Logout: limpa token e redireciona para login
  if (logoutItem) logoutItem.addEventListener('click', async () => {
    setToken(null);
    window.location.href = 'login.html';
  });
  
  // Dark Mode Toggle Handler - NOVO
  if (themeCheckbox) {
      themeCheckbox.addEventListener('change', toggleTheme);
  }

  // Modal Save (Atualizar Dados)
  const modalSaveBtn = document.getElementById('modalSave');
  if (modalSaveBtn) {
    modalSaveBtn.addEventListener('click', async () => {
      const chat = document.getElementById('modalTelegramChat').value.trim();
      const trust = document.getElementById('modalTrustedChat').value.trim();
      if (chat && !/^\d+$/.test(chat)) { alert('Seu chat_id deve conter apenas dígitos.'); return; }
      if (trust && !/^\d+$/.test(trust)) { alert('O chat_id da pessoa confiável deve conter apenas dígitos.'); return; }
      const res = await apiFetch('/api/user/telegram', 'POST', { telegram_chat_id: chat || '', trusted_telegram_id: trust || '' });
      if (res.ok) {
        alert('Dados atualizados.');
        closeModal('modalUpdate');
        fillUserInfo(); // atualiza labels
      } else {
        alert('Erro ao atualizar: ' + (res.data?.message || res.status));
      }
    });
  }

  // Config Save
  const cfgSave = document.getElementById('cfgSave');
  if (cfgSave) {
    cfgSave.addEventListener('click', () => {
      const notif = document.getElementById('cfgNotifications').value;
      const locale = document.getElementById('cfgLocale').value;
      // Salva localmente, pois o endpoint /api/user/settings não está implementado
      localStorage.setItem('cfg_notifications', notif);
      localStorage.setItem('cfg_locale', locale);
      alert('Configurações salvas localmente.');
      closeModal('modalConfig');
    });
  }

  // init - Carregar informações do usuário ao carregar a página
  if (getToken() && (btn || document.getElementById('userMenuName'))) {
    fillUserInfo();
  } else {
     // Se não há token, e não é página de auth, redireciona
     if (!window.location.pathname.endsWith('/login.html') && !window.location.pathname.endsWith('/cadastro.html') && window.location.pathname.includes('.html')) {
       // Redireciona para login se o token estiver ausente e a página não for de autenticação
       if (!getToken()) {
           window.location.href = "login.html";
       }
     }
  }
});

// --- FUNÇÃO PARA INICIALIZAR E DESENHAR O GRÁFICO DE TENDÊNCIA ---
function initializeTrendChart(currentBg, accentColor) {
    const ctx = document.getElementById('analysisTrend');

    if (!ctx) return; // Sai se o canvas não for encontrado

    // Dados de Exemplo (Devem ser substituídos por dados reais da sua API)
    const trendData = {
        labels: ['Agora', '5 min', '15 min', '30 min'],
        datasets: [{
            label: 'Glicemia (mg/dL)',
            data: [110, 105, 95, 88], // Exemplo: de 110 caindo para 88 em 30 min
            borderColor: accentColor,
            backgroundColor: 'transparent',
            borderWidth: 3,
            tension: 0.4, // Suaviza a linha
            pointRadius: 4,
            pointBackgroundColor: accentColor
        }]
    };

    const trendChart = new Chart(ctx, {
        type: 'line',
        data: trendData,
        options: {
            responsive: true,
            maintainAspectRatio: false, // Permite que o CSS controle a altura (400px definido)
            plugins: {
                legend: {
                    display: false // Não exibe a legenda
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    grid: {
                        color: currentBg, // Grid menos intrusiva
                    },
                    title: {
                        display: true,
                        text: 'Glicemia'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Chama a função após o DOM carregar (use as variáveis de cor do CSS)
document.addEventListener('DOMContentLoaded', () => {
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    const gridColor = getComputedStyle(document.documentElement).getPropertyValue('--muted').trim() + '33'; // Cor da grade clara
    initializeTrendChart(gridColor, accent);
});