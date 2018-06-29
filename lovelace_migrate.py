"""
Migration tool for Home Assistant Lovelace UI.
"""
import argparse
import logging
import sys
import json

from collections import OrderedDict
from getpass import getpass

import requests
import yaml

_LOGGER = logging.getLogger(__name__)


# Build arguments parser (argdown needs this at the beginning of the file)
parser = argparse.ArgumentParser(
    description="Home Assistant Lovelace migration tool",
    add_help=False)
parser.add_argument(
    '--help', action='help',
    help="show this help message and exit")
parser.add_argument(
    '-h', '--host', default='localhost',
    help="host of the Home Assistant server (default: localhost)")
parser.add_argument(
    '-p', '--port', default=8123,
    help="port to connect to (default: 8123)")
parser.add_argument(
    '--endpoint', default='/api',
    help="REST API endpoint (default: /api)")
parser.add_argument(
    '--ssl', dest='scheme', action='store_const',
    const='https', default='http',
    help="enable to use HTTPS")
parser.add_argument(
    '-P', '--password', nargs='?', default=False, const=None,
    help="Home Assistant API password")
parser.add_argument(
    '-n', '--name',
    help="name to give the Lovelace UI")
parser.add_argument(
    '--api-url',
    help="Home Assistant API URL (overrides above settings)")
parser.add_argument(
    '--debug', action='store_const', const=True, default=False,
    help="enable debugging")
parser.add_argument(
    '--debug-states', action='store_const', const=True, default=False,
    help="output raw states JSON")

# Parse the command line arguments
args = parser.parse_args()


def dd(*args, exit=True, json=True):
    """Debug output utility."""
    if json and len(args) == 1:
        import json as _json
        try:
            args = [_json.dumps(*args, indent=2)]
        except TypeError:
            pass
    print(*args)
    if exit:
        sys.exit()


class Lovelace(OrderedDict):
    """Lovelace migration class."""

    SIMPLE_CARDS = {
        'camera': 'camera-preview',
        'history_graph': 'history-graph',
        'media_player': 'media-control',
        'plant': 'plant-status',
        'weather': 'weather-forecast',
    }

    AUTOMATIC_CARDS = {
        'all_lights': 'light',
        'all_automations': 'automation',
        'all_devices': 'device_tracker',
        'all_fans': 'fan',
        'all_locks': 'lock',
        'all_covers': 'cover',
        'all_remotes': 'remote',
        'all_switches': 'switch',
        'all_vacuum_cleaners': 'vacuum',
        'all_scripts': 'script',
    }


    class View(OrderedDict):
        """Lovelace UI view representation."""

        def __init__(self, name=None, **kwargs) -> None:
            """Initialize view."""
            if name is not None:
                self['name'] = name
            if len(kwargs):
                self.update(kwargs)
            self['cards'] = []

            if 'tab_icon' in self and self['tab_icon'] is None:
                del self['tab_icon']

        def add_card(self, card) -> None:
            """Add card(s) to the Lovelace view."""
            cards = self['cards']
            del self['cards']
            if type(card) is list:
                cards.extend(card)
            else:
                cards.append(card)
            # Ensure cards is at the end of the OrderedDict.
            self['cards'] = cards


    class Card(OrderedDict):
        """Lovelace UI card representation."""

        def __init__(self, type=None, **kwargs):
            """Initialize automatic card."""
            if type is not None:
                self['type'] = type
            if len(kwargs):
                self.update(kwargs)

            # @todo Implement automatic sorting when OrderedDict is changed.
            first_items = ['type', 'name', 'title', 'tab_icon']
            last_items = ['views', 'cards', 'entities']
            # @todo Delete any values that are None.


    class SimpleCard(Card):
        """Lovelace UI simple card representation."""

        def __init__(self, entity_id, **kwargs):
            """Initialize simple card."""
            domain = entity_id.split('.', 1)[0]
            kwargs.setdefault('type', Lovelace.SIMPLE_CARDS[domain])
            kwargs.setdefault('entity', entity_id)
            super().__init__(**kwargs)


    class FilterCard(Card):
        """Lovelove UI automatic card representation."""

        def __init__(self, object_id=None, **kwargs):
            """Initialize automatic card."""
            kwargs.setdefault('type', 'entity-filter')
            if object_id is not None:
                kwargs.setdefault(
                    'card_config', {'title': name_from_id(object_id)})
                kwargs.setdefault(
                    'filter', [{'domain': Lovelace.AUTOMATIC_CARDS[object_id]}])
            super().__init__(**kwargs)


    class EntitiesCard(Card):
        """Lovelove UI entities card representation."""

        def __init__(self, title=None, **kwargs):
            """Initialize automatic card."""
            kwargs.setdefault('type', 'entities')
            if title is not None:
                kwargs.setdefault('title', title)
            kwargs.setdefault('entities', [])
            super().__init__(**kwargs)

        def add_entity(self, entity) -> None:
            """Add entity(s) to the card."""
            entities = self['entities']
            del self['entities']
            if type(entity) is list:
                entities.extend(entity)
            else:
                entities.append(entity)
            # Ensure entities is at the end of the OrderedDict
            self['entities'] = entities


    def __init__(self, groups, name="Home"):
        """Convert existing Home Assistant groups to Lovelace UI."""
        self.groups = groups

        self['name'] = name
        views = self['views'] = []

        if 'default_view' in self.groups:
            views.append(self.convert_view(self.groups['default_view'],
                                           'default_view'))

        for name, conf in self.groups.items():
            if name == 'default_view':
                continue
            if not conf.get('view', False):
                continue
            views.append(self.convert_view(conf, name))

        view = Lovelace.View("All Entities", tab_icon='mdi:settings')
        view.add_card(Lovelace.FilterCard(
            card_config={'title': "All Entities"}, filter=[{}]))

        views.append(view)

    def convert_card(self, entity_id) -> Card:
        """Helper to convert a card to Lovelace UI."""
        domain, object_id = entity_id.split('.', 1)

        if domain == 'group':
            if object_id not in self.groups:
                _LOGGER.warning("Couldn't find group with entity "
                                "id {}".format(entity_id))
                return None

            if object_id in Lovelace.AUTOMATIC_CARDS:
                return Lovelace.FilterCard(object_id)

            return self.convert_group(self.groups[object_id], entity_id)

        if domain in Lovelace.SIMPLE_CARDS:
            return Lovelace.SimpleCard(entity_id)

        _LOGGER.warning("Cannot determine card type for entity id '{}'. "
                        "Maybe it is unsupported?".format(entity_id))
        return None

    def convert_group(self, config, name) -> (Card, list):
        """Helper to convert a group to Lovelace UI."""
        if config.get('view', False):
            _LOGGER.error("Cannot have view group '{}' inside "
                          "another group".format(name))
            return None

        card = Lovelace.EntitiesCard(config.get('friendly_name', name_from_id(name)))
        extra_cards = []
        for entity_id in config.get('entity_id', []):
            domain, object_id = entity_id.split('.', 1)
            if domain in ['group', 'media_player', 'camera', 'history_graph',
                          'media_player', 'plant', 'weather']:
                _LOGGER.warning(
                    "Cannot have domain '{}' within a non-view group {}! "
                    "I will put it into the parent view-type group.".format(
                    domain, name))
                extra_card = self.convert_card(entity_id)
                if extra_card is not None:
                    extra_cards.append(extra_card)
                continue
            card.add_entity(entity_id)
        return card, extra_cards

    def convert_view(self, config, name) -> Card:
        """Helper to convert a view to Lovelace UI."""
        view = Lovelace.View(
            config.get('friendly_name', name_from_id(name)),
            tab_icon=config.get('icon'))

        for entity_id in config.get('entity_id', []):
            card = self.convert_card(entity_id)
            if card is None:
                continue
            if isinstance(card, tuple):
                # @todo Fix this to use only one call.
                view.add_card(card[0])
                view.add_card(card[1])
            else:
                view.add_card(card)

        return view


class HomeAssistantAPI(object):
    """Class to access Home Assistant REST API."""

    def __init__(self, api_url, password=None):
        """Initialize the class object."""
        self.cache = {}
        self.api_url = api_url

        if password is None:
            password = self.auth()
        self.password = password

    def auth(self):
        """Prompt user to enter a password."""
        try:
            return getpass("Enter password: ")
        except KeyboardInterrupt:
            print()
            sys.exit(130)

    def get(self, endpoint='/', refresh=False):
        """Wrapper to send a GET request to Home Assistant API."""
        if endpoint in self.cache and not refresh:
            return self.cache[endpoint]

        url = self.api_url + endpoint
        headers = {'x-ha-access': self.password or '',
                   'content-type': 'application/json'}

        request = requests.get(url, headers=headers)

        if request.status_code == requests.codes.unauthorized:
            self.password = auth()
            return self.get(endpoint=endpoint, refresh=refresh)
        else:
            request.raise_for_status()

        self.cache[endpoint] = request
        return request

    def get_config(self, **kwargs) -> dict:
        """Get config from Home Assistant REST API."""
        request = self.get('/config', **kwargs)
        return request.json()

    def get_states(self, **kwargs) -> dict:
        """Get states from Home Assistant REST API."""
        request = self.get('/states', **kwargs)
        return request.json()


def get_entities(states) -> dict:
    """Build a list of entities from states JSON."""
    entities = {}
    for e in states:
        domain = e['entity_id'].split('.', 1)[0]
        if domain not in entities:
            entities[domain] = []
        entities[domain].append(e)
    return entities


def name_from_id(object_id) -> str:
    """Generate a friendly name from an object_id."""
    return object_id.replace('_', ' ').title()


def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwargs) -> str:
    """YAML dumper for OrderedDict."""

    class OrderedDumper(Dumper):
        """Wrapper class for YAML dumper."""

        def ignore_aliases(self, data):
            """Disable aliases in YAML dump."""
            return True

        def increase_indent(self, flow=False, indentless=False):
            """Increase indent on YAML lists."""
            return super(OrderedDumper, self).increase_indent(flow, False)

    def _dict_representer(dumper, data):
        """Function to represent OrderDict and derivitives."""
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    OrderedDumper.add_representer(Lovelace, _dict_representer)
    OrderedDumper.add_representer(Lovelace.View, _dict_representer)
    OrderedDumper.add_representer(Lovelace.Card, _dict_representer)
    OrderedDumper.add_representer(Lovelace.SimpleCard, _dict_representer)
    OrderedDumper.add_representer(Lovelace.FilterCard, _dict_representer)
    OrderedDumper.add_representer(Lovelace.EntitiesCard, _dict_representer)

    return yaml.dump(data, stream, OrderedDumper, **kwargs)


def main() -> int:
    """Main program function."""
    global args

    logging.basicConfig(level=logging.INFO)

    try:
        from colorlog import ColoredFormatter
        logging.getLogger().handlers[0].setFormatter(ColoredFormatter(
            "%(log_color)s%(levelname)s %(message)s%(reset)s",
            datefmt="",
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red',
            }
        ))
    except ImportError:
        pass

    # Get UI name from args
    ui_name = args.name

    # Check if a file was provided via stdin
    if not sys.stdin.isatty():
        # Read states JSON from stdin
        states = json.load(sys.stdin)
    else:
        # Build api_url if not specified
        if args.api_url is None:
            args.api_url = "{scheme}://{host}:{port}{endpoint}".format(**vars(args))

        # Instantiate new Home Assistant API object
        hass = HomeAssistantAPI(args.api_url, args.password)

        # Get states from REST API
        states = hass.get_states()

        # Detect UI name from config if not provided via args
        if ui_name is None:
            config = hass.get_config()
            ui_name = config.get('location_name')

    # Output states for debugging
    if args.debug_states:
        print(json.dumps(states, indent=2))
        return 0

    # Build a list of entities from the states
    entities = get_entities(states)

    # Set UI name if we still don't have one
    if ui_name is None:
        ui_name = 'Home'

    # Build groups dictionary to pass to Lovelace converter
    groups = {}
    for g in entities['group']:
        object_id = g['entity_id'].split('.', 1)[1]
        groups[object_id] = g.get('attributes')

    # Convert to Lovelace UI
    lovelace = Lovelace(groups, name=ui_name)
    dump = ordered_dump(lovelace, Dumper=yaml.SafeDumper,
          default_flow_style=False)

    # Output Lovelace YAML to stdout
    if not args.debug:
        print(dump.strip())

    # Return with a normal exit code
    return 0


if __name__ == '__main__':
    sys.exit(main())
