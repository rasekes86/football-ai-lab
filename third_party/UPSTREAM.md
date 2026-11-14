# Proveniencia de skills externas

Se han copiado archivos de los siguientes repositorios públicos MIT. Se conservaron las licencias en third_party/licenses/. Estos SHA corresponden a las versiones consultadas en noviembre de 2026:

- [machina-sports/sports-skills](https://github.com/machina-sports/sports-skills) — `547d36590eab32cb6b750b0fb0b51844c3be4676`
- [quangtm210395/predicting-football-matches](https://github.com/quangtm210395/predicting-football-matches) — `2d02330a50ff20a9e9b8cb4c4ebfdcfba108644e`
- [infersports/infersports-skill](https://github.com/infersports/infersports-skill) — `be079875b62a6af00fd9c16860cec6cb4168b654`
- [RW-git-hub/claude-quant](https://github.com/RW-git-hub/claude-quant) — `f96a2628128c5e707c52117992dcc6149dd682e4`

## Alcance de integración

Las skills de Machina football-data, Football Match Predictor e InferSports están **disponibles para Codex y Claude Code** en las carpetas .agents/skills y .claude/skills. No se cargan ni ejecutan automáticamente durante los workflows de GitHub Actions. Claude Quant se incorpora mediante una skill de auditoría adaptada y una referencia específica. El motor diario es Python autónomo y la API opcional de cuotas usa The Odds API con activación explícita. Las fuentes públicas pueden cambiar y sus condiciones de uso se aplican por separado.
