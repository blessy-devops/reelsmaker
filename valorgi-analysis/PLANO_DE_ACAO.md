# 🎬 Plano de Ação: Análise dos Vídeos Valorde

## 📊 Visão Geral

**Objetivo**: Transcrever e analisar estrategicamente os 42 vídeos mais virais do Valorde para criar templates de roteiro e agentes de IA.

**Vídeos encontrados**: 42 arquivos (1 duplicado detectado)
**Whisper disponível**: `openai-whisper` via pip
**Idioma dos vídeos**: Inglês (conta americana de motivação)

---

## 🗂️ Estrutura de Pastas

```
valorde-analysis/
├── PLANO_DE_ACAO.md           # Este documento
├── INDICE_GERAL.md            # Índice com todos os vídeos e categorias
├── videos/                     # Vídeos renomeados
│   ├── video_01.mp4
│   ├── video_02.mp4
│   └── ...
├── transcricoes/              # Transcrições puras
│   ├── transcricao_video_01.md
│   ├── transcricao_video_02.md
│   └── ...
├── analises/                  # Análises estratégicas
│   ├── analise_video_01.md
│   ├── analise_video_02.md
│   └── ...
└── resumo/                    # Documentos finais de síntese
    ├── CATEGORIAS.md          # Categorização de todos os estilos
    ├── PADROES_NARRATIVOS.md  # Padrões identificados
    └── TEMPLATES_ROTEIRO.md   # Templates para agentes (fase futura)
```

---

## 📋 Etapas do Plano

### FASE 1: Preparação e Organização (5 min)

1. **Criar estrutura de pastas**
   - Criar `valorde-analysis/` com subpastas
   - Adicionar ao `.gitignore` do viralyzer-web-app

2. **Copiar e renomear vídeos**
   - Ordenar por timestamp (data de postagem)
   - Renomear para `video_01.mp4`, `video_02.mp4`, etc.
   - Remover arquivo duplicado
   - Criar mapeamento: nome original → nome novo

---

### FASE 2: Transcrição com Whisper (40-60 min estimado)

**Configuração do Whisper:**
- Modelo: `medium` ou `large-v3` (melhor qualidade para inglês)
- Idioma: `en` (inglês)
- Formato de saída: texto puro + timestamps

**Execução:**
- Rodar transcrições em paralelo (múltiplos terminais)
- Dividir em batches de ~10 vídeos cada
- 4 processos paralelos para maximizar eficiência

**Para cada vídeo gerar:**
```markdown
# Transcrição - Vídeo XX

**Arquivo original**: valorgi_XXXXX.mp4
**Arquivo renomeado**: video_XX.mp4
**Duração**: XX:XX
**Data de transcrição**: YYYY-MM-DD

---

## Transcrição Completa

[texto transcrito aqui]
```

---

### FASE 3: Análise Estratégica (via Sub-agents Claude)

**Para cada vídeo, criar documento de análise com:**

```markdown
# Análise Estratégica - Vídeo XX

## Metadados
- **Arquivo**: video_XX.mp4
- **Duração**: XX:XX
- **Categoria**: [a ser definida]

---

## Transcrição Completa
[cópia da transcrição]

---

## Análise do Roteiro

### 1. Categoria/Estilo do Vídeo
- [ ] História de pessoa famosa
- [ ] Lições de vida / Filosofia
- [ ] X dicas sobre Y
- [ ] X tipos de pessoa
- [ ] Citação + reflexão
- [ ] História inspiracional anônima
- [ ] Outro: ___________

### 2. Estrutura Narrativa

#### Hook (Abertura) - primeiros 3-5 segundos
- **Tipo de gancho**:
- **Texto exato**:
- **Por que funciona**:

#### Desenvolvimento
- **Estrutura**:
- **Elementos-chave**:
- **Progressão emocional**:

#### Clímax/Ponto de Virada
- **Momento**:
- **Impacto emocional**:

#### Fechamento/CTA
- **Tipo**:
- **Texto exato**:

### 3. Outline Dissecado

[Lista numerada com cada "beat" do roteiro]

### 4. Elementos de Viralização

- **Emoção principal evocada**:
- **Gatilhos psicológicos**:
- **Universalidade do tema**:
- **Quotability** (frases compartilháveis):

### 5. Padrões Técnicos

- **Duração total**:
- **Ritmo de fala** (lento/médio/rápido):
- **Pausas estratégicas**:
- **Tom de voz**:

### 6. Aplicabilidade

- **Pode ser adaptado para nicho brasileiro?**:
- **Dificuldade de replicação** (1-5):
- **Elementos únicos a preservar**:
```

---

### FASE 4: Categorização e Síntese

1. **Após todas as análises**, criar:
   - `CATEGORIAS.md` - Lista de todas as categorias identificadas
   - `PADROES_NARRATIVOS.md` - Padrões recorrentes
   - `INDICE_GERAL.md` - Tabela com todos os vídeos

2. **Índice terá formato:**
   | # | Vídeo | Categoria | Hook | Duração | Tema Principal |
   |---|-------|-----------|------|---------|----------------|

---

## ⚙️ Estratégia de Execução

### Paralelização

Para maximizar eficiência e não explodir contexto:

1. **Transcrição** (4 processos paralelos em background)
   ```bash
   # Terminal 1: videos 01-11
   # Terminal 2: videos 12-22
   # Terminal 3: videos 23-33
   # Terminal 4: videos 34-42
   ```

2. **Análise** (Sub-agents Claude em paralelo)
   - Dividir vídeos em batches de 5-7
   - Cada sub-agent analisa um batch
   - Resultados consolidados no final

### Controle de Qualidade

- Verificar cada transcrição tem conteúdo
- Verificar cada análise segue o template
- Cross-check categorias ao final

---

## 📝 Entregáveis Finais

1. ✅ 41 vídeos renomeados e organizados (excluindo duplicata)
2. ✅ 41 documentos de transcrição (`transcricao_video_XX.md`)
3. ✅ 41 documentos de análise (`analise_video_XX.md`)
4. ✅ `INDICE_GERAL.md` com tabela completa
5. ✅ `CATEGORIAS.md` com categorização
6. ✅ `PADROES_NARRATIVOS.md` com insights

---

## ⏱️ Próximos Passos (Fase Futura - NÃO executar agora)

- Criar templates de roteiro baseados nos padrões
- Desenvolver agentes para geração de scripts
- Desenvolver agente para sugestão de ideias

---

## 🚨 Notas Importantes

- Arquivo duplicado detectado: `valorgi_1736889735_...mp4` e `valorgi_1736889735_...(1).mp4`
- Todos os vídeos serão adicionados ao `.gitignore`
- Transcrições e análises em inglês (conteúdo original) ou português (sua escolha)?

---

**Aguardando sua confirmação para iniciar a execução!** 🚀
