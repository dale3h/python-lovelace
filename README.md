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
    python3 lovelace_migrate.py [-h] [-n <name>] [-p [<password>]] [<api-url|file>]
```

### Arguments

#### Quick reference table

|Short|Long        |Default|Description                                 |
|-----|------------|-------|--------------------------------------------|
|`-h` |`--help`    |       |show this help message and exit             |
|`-n` |`--name`    |`None` |name to give the Lovelace UI (default: auto)|
|`-p` |`--password`|       |Home Assistant API password                 |

#### `-h`, `--help`
show this help message and exit

#### `-n`, `--name` (Default: auto)
name to give the Lovelace UI

#### `-p`, `--password`
Home Assistant API password
