# Proteção de Dados na Automação

## Problema Identificado
O script `scripts/build_profile_data.py` sobrescrevia completamente o `profile.json` com dados do LinkedIn, **perdendo experiências antigas** (2013-2015) que não estão mais no perfil do LinkedIn.

## Solução Implementada
Modificado o script para **preservar automaticamente** experiências anteriores a 2016:

1. Lê o `profile.json` existente antes de sobrescrever
2. Identifica experiências com ano inicial < 2016
3. Mescla dados do LinkedIn + experiências antigas preservadas
4. Salva o resultado combinado

## Experiências Protegidas
As seguintes experiências são **preservadas automaticamente** na automação:

- **Rede Vivo** (Fev 2013 - Jun 2013)
- **Grupo Rigon** (Ago 2013 - Out 2015)
- **Go Up Software (Viasoft)** (Out 2015 - Mar 2016)

## Como Funciona
```python
# O script agora:
# 1. Carrega profile.json existente
existing_profile = read_json(output_path)
existing_timeline = existing_profile.get("timeline", [])

# 2. Identifica experiências antes de 2016
for exp in existing_timeline:
    year = extract_year(exp["period"])
    if year < 2016:
        preserved_experiences.append(exp)

# 3. Combina LinkedIn + experiências antigas
combined_timeline = linkedin_timeline + preserved_experiences
```

## Resultado
Ao rodar `python3 scripts/build_profile_data.py`:
```
✓ Merged profile data saved to profile.json
  - LinkedIn experiences: 6
  - Preserved old experiences: 3
  - Total timeline entries: 9
```

## Workflow Automático
O GitHub Actions workflow `.github/workflows/update-profile.yml` executa este script periodicamente. Agora as experiências antigas **não serão perdidas** nas atualizações automáticas.

## Como Adicionar Novas Experiências Antigas
1. Edite `assets/data/profile.json` manualmente
2. Adicione a experiência no array `timeline`
3. Use período com ano < 2016 para proteção automática
4. Commit e push - o script preservará automaticamente

---
**Data da modificação**: 24/01/2026
**Script modificado**: `scripts/build_profile_data.py`
