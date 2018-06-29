# python-lovelace
Lovelace UI module and migration tool for Python

## Requirements

```shell
$ pip3 install requests pyyaml
```

## Arguments and Usage

### Usage

```
usage:
    python3 lovelace_migrate.py [--help] [-h HOST] [-p PORT]
        [--endpoint ENDPOINT] [--ssl] [-P [PASSWORD]] [-n NAME]
        [--api-url API_URL] [--debug] [--debug-states]
```

### Arguments

#### Quick reference table

|Short|Long            |Default    |Description                                           |
|-----|----------------|-----------|------------------------------------------------------|
|     |`--help`        |           |show this help message and exit                       |
|`-h` |`--host`        |`localhost`|host of the Home Assistant server (default: localhost)|
|`-p` |`--port`        |`8123`     |port to connect to (default: 8123)                    |
|     |`--endpoint`    |`/api`     |REST API endpoint (default: /api)                     |
|     |`--ssl`         |`http`     |enable to use HTTPS                                   |
|`-P` |`--password`    |           |Home Assistant API password                           |
|`-n` |`--name`        |`None`     |name to give the Lovelace UI                          |
|     |`--api-url`     |`None`     |Home Assistant API URL (overrides above settings)     |
|     |`--debug`       |           |enable debugging                                      |
|     |`--debug-states`|           |output raw states JSON                                |

#### `--help`
show this help message and exit

#### `-h`, `--host` (Default: localhost)
host of the Home Assistant server (default: localhost)

#### `-p`, `--port` (Default: 8123)
port to connect to (default: 8123)

#### `--endpoint` (Default: /api)
REST API endpoint (default: /api)

#### `--ssl` (Default: http)
enable to use HTTPS

#### `-P`, `--password`
Home Assistant API password

#### `-n`, `--name` (Default: None)
name to give the Lovelace UI

#### `--api-url` (Default: None)
Home Assistant API URL (overrides above settings)

#### `--debug`
enable debugging

#### `--debug-states`
output raw states JSON
