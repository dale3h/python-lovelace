# python-lovelace
Lovelace UI module and migration tool for Python

## Requirements
- pip3
- PyYAML
- requests

On Raspbian Stretch `pip3` is not installed by default. To install `pip3`, run:
```shell
$ sudo apt-get install python3-pip
```

After you clone this repository, you can run:
```shell
$ pip3 install -r requirements.txt
```

To install without the `requirements.txt` file:
```shell
$ pip3 install "requests>=2.14.2" "pyyaml>=3.11,<4"
```

### Usage
```shell
$ python3 lovelace_migrate.py [-h] [-t <title>] [-p [<password>]] [<api-url|file>]
```

### Examples
#### Prompt for Password (Recommended)
You will be prompted to enter your API password if you use [`-p`][arg-pass]
without specifying a password.

```shell
$ python3 lovelace_migrate.py -p http://192.168.1.100:8123/api
```

#### Remote with HTTPS/SSL (Recommended)
The migration script can use a remote URL to pull the entity configuration. It
is only recommended to use this option if your server has HTTPS enabled.

```shell
$ python3 lovelace_migrate.py -p https://your.domain.com/api
```

#### Password in Command (Not Recommended)
It is not recommended to enter your password into the command because it is
possible that it will be stored in your command history.

```shell
$ python3 lovelace_migrate.py -p YOUR_API_PASSWORD http://192.168.1.100:8123/api
```

#### Password Detection (Not Recommended)
This will attempt to connect to your Home Assistant server without a password,
and if it requires authentication you will be prompted to enter your password.

```shell
$ python3 lovelace_migrate.py -p YOUR_API_PASSWORD http://192.168.1.100:8123/api
```

***Note:** If you have [`login_attempts_threshold`][http-component] set to a
low number, it is possible that you might ban yourself by using the password
detection method.*

#### Local File as Input
A local JSON file can be used as the configuration input.

```shell
$ python3 lovelace_migrate.py -t Home states.json
```

***Note:** Loading from file is currently not implemented. For a temporary
workaround, please see [Using `cat`][using-cat].*

#### Use Contents of `stdin`
You can even use the contents of `stdin` as the configuration for the script:

##### Using `cat`
```shell
$ cat .data/entities.json | python3 lovelace_migrate.py -t Home -
```

##### Using `curl`
```shell
$ curl -sSL -X GET \
       -H "x-ha-access: YOUR_PASSWORD" \
       -H "content-type: application/json" \
       http://192.168.1.100:8123/api/states \
       | python3 lovelace_migrate.py -
```

***Note:** When using a file or `stdin` as input, the default title for the
Lovelove UI will be set to **Home**. You can override this using the [`-t` (or
`--title`) argument][arg-title].*

### Arguments
#### Quick reference table

|Short|Long        |Default|Description                                       |
|-----|------------|-------|--------------------------------------------------|
|`-h` |`--help`    |       |show this help message and exit                   |
|`-t` |`--title`   |`Home` |title of the Lovelace UI                          |
|`-p` |`--password`|       |Home Assistant API password                       |
|     |`<api-url>` |       |Home Assistant API URL (ending with `/api`)       |
|     |`<file>`    |       |local JSON file containing dump from `/api/states`|

#### `-h`, `--help`
This argument will show the usage help and immediately exit.

#### `-t`, `--title`
This is the title that you wish to be set for the Lovelace UI. The default
is **Home**.

#### `-p`, `--password`
Home Assistant API password. If this argument is enabled without specifying a
password, you will be prompted to enter your password.

#### `<api-url|file>`
##### `<api-url>`
It is recommended to use your API URL as the input when migrating to Lovelace
UI. This URL usually ends with `/api`, and commonly looks something like:

- `http://192.168.1.100:8123/api`
- `https://your.domain.com/api`
- `https://my-domain.duckdns.org/api`

#### `<file>`
You can also load your configuration from a local file. This file must contain
the same format as the data from [`/api/states`][api-states].

***Note:** Use `-` as the `<api-url|file>` to load configuration from `stdin`.

[api-states]: https://developers.home-assistant.io/docs/en/external_api_rest.html#get-api-states
[arg-title]: #-t---title
[arg-pass]: #-p---password
[http-component]: https://www.home-assistant.io/components/http/
[using-cat]: #using-cat
