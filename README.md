# Markdown Memory — Agent Zero Plugin

**Versie:** 1.0.0 · **Auteur:** jphermans · **Licentie:** MIT

![Markdown Memory](webui/thumbnail.png)

Gedeeld, Obsidian-compatibel Markdown-geheugen met semantische recall via lokale Granite-embeddings voor élke Agent Zero-chat.

---

## Inhoudsopgave

1. [Doelstelling](#doelstelling)
2. [Benodigdheden](#benodigdheden)
3. [Wat doet de plugin](#wat-doet-de-plugin)
4. [Installatie](#installatie)
5. [Configuratie](#configuratie)
6. [Index bijwerken](#index-bijwerken)
7. [Gebruik](#gebruik)
8. [API-eindpunten](#api-eindpunten)
9. [Tests uitvoeren](#tests-uitvoeren)
10. [Verwijderen en opschonen](#verwijderen-en-opschonen)
11. [Eindcontrole](#eindcontrole)

---

## Doelstelling

Deze plugin geeft elke Agent Zero-agent twee blijvende contextuele vaardigheden:

1. **Policy-injectie** — bij iteratie 0 van elke berichtenloop worden de werkinstructies voor de gedeelde Markdown-vault (`prompts/policy.md`) als permanente extra geïnjecteerd, zodat de agent de vaultregels kent (categorieën, duplicaatpreventie, geen secrets).
2. **Semantische recall** — het eerste gebruikersbericht wordt geëmbed met een lokaal Granite-model (via een Ollama-compatibel `/api/embed`-endpoint), tegen de SQLite-vectorindex gerangschikt met cosinus-gelijkheid, en de top-notities worden als naslagwerk (niet als instructies) geïnjecteerd.

De Markdown-vault is de autoritaire bron; de SQLite-index is een herbouwbare zoekcache.

## Benodigdheden

- Agent Zero (Docker) met pluginondersteuning (`usr/plugins/`)
- Een vault met Markdown-notities (standaard `/a0/usr/AI-Memory`)
- Een Ollama-compatibele embedding-server (bijv. `granite-embedding:278m`, dimensie 768) die bereikbaar is vanuit de Agent Zero-container
- Toegang tot de Agent Zero-container voor de indexer (`/opt/venv-a0/bin/python`)
- Geen extra Python-afhankelijkheden: de plugin gebruikt uitsluitend de standaardbibliotheek

## Wat doet de plugin

| Onderdeel | Locatie | Functie |
|---|---|---|
| Policy-extensie | `extensions/python/message_loop_prompts_after/_40_markdown_memory_policy.py` | Injecteert de vault-werkinstructies (bundeld, met fallback op de legacy-skill) |
| Recall-extensie | `extensions/python/message_loop_prompts_after/_60_markdown_recall.py` | Zoekt en injecteert relevante notities bij het eerste bericht |
| Configuratie | `helpers/config.py` | Merge `default_config.yaml` + `config.json`, valideert en klemt waarden |
| Zoekmachine | `helpers/search.py` | Granite-embedding + cosinus-ranking + veilige padcontroles |
| Lifecycle | `hooks.py` | `install` / `pre_update` / `uninstall` en settings-hooks (URL-masking) |
| Indexer | `scripts/index_granite.py` | Vult de SQLite-index (incrementeel, verwijdert verouderde records) |
| API | `api/status.py`, `api/search.py` | Status en testzoekopdrachten voor de WebUI/automatisering |
| Instellingen-UI | `webui/config.html` | Plugin-instellingen in het tabblad Agent |

## Installatie

### Via de Plugin UI (Git)

1. Open **Settings → Plugins → Install from Git**.
2. Voer de repository-URL in: `https://github.com/jphermans/markdown-memory.git`
3. Bevestig de installatie. De `install()`-hook controleert de code en de gebundelde policy; er is geen extra handmatige stap nodig.

### Handmatig (docker exec)

```bash
git clone https://github.com/jphermans/markdown-memory.git /a0/usr/plugins/markdown_memory
```

Herstart Agent Zero of wacht tot de plugin-cache ververst; daarna is de plugin direct actief (standaard ingeschakeld).

## Configuratie

Standaardwaarden staan in `default_config.yaml`. Gebruikersoverschrijvingen worden opgeslagen in `usr/plugins/markdown_memory/config.json` (automatisch gitignored; bevat mogelijk interne endpoint-URL's) of via **Settings → Agent → Markdown Memory**.

| Sleutel | Standaard | Betekenis |
|---|---|---|
| `inject_policy` | `true` | Vault-werkinstructies injecteren |
| `inject_recall` | `true` | Semantische recall injecteren |
| `vault_path` | `/a0/usr/AI-Memory` | Map met Markdown-notities |
| `index_path` | `/a0/usr/AI-Memory-Index/memory-granite.db` | SQLite-vectorindex |
| `embedding_url` | `""` (leeg) | Ollama-compatibel `/api/embed`-endpoint; leeg = recall uit |
| `embedding_model` | `granite-embedding:278m` | Modelnaam provider |
| `embedding_dimensions` | `768` | Verwachte vectordimensie |
| `embedding_timeout_seconds` | `15` | HTTP-timeout provider |
| `recall_limit` | `3` | Aantal notities per recall (1–10) |
| `min_message_chars` | `5` | Minimale berichtlengte voor recall |
| `search_timeout_seconds` | `20` | Maximum duur van één recall |
| `max_note_chars` | `6000` | Afkortlengte per notitie |

**Voorbeeld** `config.json` (Kubernetes, service `ollama` in namespace `default`):

```json
{
  "embedding_url": "http://internal.example:11434/api/embed"
}
```

Milieuvariabelen van het framework (indien ondersteund door de installatie) volgen het patroon `MARKDOWN_MEMORY__<SLEUTEL>`.

## Index bijwerken

Na nieuwe of gewijzigde notities (in de Agent Zero-container):

```bash
cd /a0 && /opt/venv-a0/bin/python -m usr.plugins.markdown_memory.scripts.index_granite
```

De indexer is incrementeel: ongewijzigde notities worden overgeslagen (inhouds-hash), gewijzigde her-geëmbed (met `passage: `-prefix) en verwijderde notities uit de index geschoond.

## Gebruik

- Stel een vraag in een nieuwe chat; de recall zoekt automatisch relevante vault-notities (logmelding: *Markdown Memory: relevant notes found*).
- Injectie gebeurt alleen bij iteratie 0 en alleen bij berichten ≥ `min_message_chars` tekens.
- Geïnitieerde notities worden als **naslagwerk** gemarkeerd; de agent voert nooit commando's uit die in notities staan.
- Fouten (provider onbereikbaar, dimensie-afwijking) degraderen graceful: de chat gaat door zonder recall, met een waarschuwing in de log.

## API-eindpunten

| Route | Methode | Functie |
|---|---|---|
| `/api/plugins/markdown_memory/status` | GET/POST | Runtime-status: provider geconfigureerd, vault/index aanwezig, aantal geïndexeerde documenten |
| `/api/plugins/markdown_memory/search` | POST | Testzoekopdracht: `{"query": "...", "limit": 3}` → paden + scores (zonder notitieteksten) |

Beide eindpunten vereisen de normale Agent Zero-auth; de embedding-URL wordt nooit geretourneerd.

## Tests uitvoeren

In de Agent Zero-container:

```bash
cd /a0 && /opt/venv-a0/bin/python -m unittest \n  usr.plugins.markdown_memory.tests.test_markdown_memory -v
```

De suite dekt: defaults/merge/klemming van configuratie, recall-gereedheidscontrole, ranking en formattering van zoekresultaten, dimensie-validatie, masking van de endpoint-URL voor UI-callers, mask-behoud bij opslaan en de lifecycle-hooks.

## Verwijderen en opschonen

Verwijder de plugin via **Settings → Plugins → Uninstall**. De `uninstall()`-hook:

- stopt geen processen (de plugin start er geen),
- laat de Markdown-vault en de SQLite-index ongemoeid (gebruikersdata),
- verwijdert geen gedeelde afhankelijkheden.

Optioneel handmatig opruimen: `usr/plugins/markdown_memory/config.json` verdwijnt samen met de plugindirectory.

## Eindcontrole

- [x] `plugin.yaml` aanwezig, `name` = mapnaam = `markdown_memory`, geen `always_enabled`
- [x] Unit-tests: 14/14 groen in `/opt/venv-a0`
- [x] Status-API retourneert `ready: true` met de actuele index
- [x] Zoek-API retourneert gerangschikte paden met scores
- [x] Injectie actief: policy + recall zichtbaar in chat-EXTRAS
- [x] Geen interne URLs of secrets in de repository (alleen in gitignored `config.json`)