# Como Adicionar Fotos Reais dos Perfis LinkedIn

## 📁 Estrutura de Pastas Criada

```
assets/img/profiles/
├── companies/          # Logos das empresas
│   ├── educbank.jpg
│   ├── otocrm.jpg
│   ├── deepesg.jpg
│   ├── herospark.jpg
│   └── grupovoalle.jpg
└── people/            # Fotos das pessoas
    ├── rafael-carvalho.jpg
    ├── allan-ribeiro.jpg
    ├── lucas-brandao.jpg
    ├── fernando-viegas.jpg
    ├── guilherme-maduro.jpg
    └── jaquelyne-kelm.jpg
```

## 📥 Como Baixar as Fotos

### Empresas (Timeline de Carreira)

1. **Educbank**: https://www.linkedin.com/company/educbank/
   - Abra o link, clique com botão direito na logo da empresa
   - "Salvar imagem como..." → `assets/img/profiles/companies/educbank.jpg`

2. **Oto CRM**: https://www.linkedin.com/company/otocrm/
   - Salvar como: `assets/img/profiles/companies/otocrm.jpg`

3. **DEEP ESG**: https://www.linkedin.com/company/deepesg/
   - Salvar como: `assets/img/profiles/companies/deepesg.jpg`

4. **HeroSpark**: https://www.linkedin.com/company/herospark/
   - Salvar como: `assets/img/profiles/companies/herospark.jpg`

5. **Grupo Voalle**: https://www.linkedin.com/company/grupovoalle/
   - Salvar como: `assets/img/profiles/companies/grupovoalle.jpg`

### Pessoas (Recomendações)

1. **Rafael Carvalho**: https://www.linkedin.com/in/rafaelmcarvalho/
   - Salvar foto como: `assets/img/profiles/people/rafael-carvalho.jpg`

2. **Allan Ribeiro**: https://www.linkedin.com/in/allanggribeiro/
   - Salvar foto como: `assets/img/profiles/people/allan-ribeiro.jpg`

3. **Lucas Brandão**: https://www.linkedin.com/in/lucas-brandao-pro/
   - Salvar foto como: `assets/img/profiles/people/lucas-brandao.jpg`

4. **Fernando Viegas**: https://www.linkedin.com/in/fernandoviegas92/
   - Salvar foto como: `assets/img/profiles/people/fernando-viegas.jpg`

5. **Guilherme Maduro**: https://www.linkedin.com/in/guilhermemaduro/
   - Salvar foto como: `assets/img/profiles/people/guilherme-maduro.jpg`

6. **Jaquelyne Kelm**: https://www.linkedin.com/in/jaquelyne-kelm/
   - Salvar foto como: `assets/img/profiles/people/jaquelyne-kelm.jpg`

## ⚡ Processo Rápido

1. Abra cada link no navegador
2. Clique com botão direito na foto/logo
3. "Salvar imagem como..."
4. Salve com o nome exato listado acima na pasta correta
5. Após baixar todas, execute: `python scripts/build_profile_data.py`

## 🔄 Após Adicionar as Fotos

Os arquivos JSON serão automaticamente atualizados para usar as imagens locais.
O site carregará as fotos reais dos perfis!

---

**Dica**: Para fotos de melhor qualidade, você pode usar ferramentas de desenvolvedor do navegador (F12) para encontrar a URL da imagem em alta resolução.
