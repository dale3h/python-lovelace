"""
Migration tool for Home Assistant Lovelace UI.
"""
# @todo Finish adding sorting to everywhere else (and remove existing "sort" code)
# @todo Add sorting to Lovelace.View

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
    description="Home Assistant Lovelace migration tool")

# Positional arguments
parser.add_argument(
    'input', metavar='<api-url|file>', nargs='?', default='-',
    help="Home Assistant REST API URL or states JSON file")

# Optional arguments
parser.add_argument(
    '-n', '--name', metavar='<name>',
    help="name to give the Lovelace UI (default: auto)")
# parser.add_argument(
#     '-o', '--output', metavar='<file>',
#     help="write output to <file> instead of stdout")
parser.add_argument(
    '-p', '--password', metavar='<password>', nargs='?',
    default=False, const=None,
    help="Home Assistant API password")
parser.add_argument(
    '--debug', action='store_true',
    help="set log level to DEBUG")

# Parse the args
args = parser.parse_args()


def dd(msg=None, j=None, *args):
    if j is None and len(args) == 0:
        j = msg
        msg = "{}"
    if j is not None:
        _LOGGER.debug(msg.format(json.dumps(j, indent=2)))
    else:
        _LOGGER.debug(msg.format(*args))


class LovelaceBase(OrderedDict):
    """
    Base class for Lovelace objects.

    Derivitives should set `key_order`:

    self.key_order = ['first', 'second', '...', 'last']
    """

    def __init__(self, **kwargs):
        """Initialize the object."""
        self.update(kwargs)

        for key, value in self.items():
            if value is None:
                del self[key]

    @classmethod
    def from_config(cls, config):
        """
        Subclass should implement config conversion methods `from_xxx_config`:

        from_camera_config(cls, config)
        from_media_player_config(cls, config)
        from_group_config(cls, config)
        """
        try:
            domain = config['entity_id'].split('.', 1)[0]
            fx = getattr(cls, "from_" + domain + "_config", None)
            if fx is None:
                _LOGGER.error("Class '{}' does not support conversion from "
                              "'{}' config".format(cls.__name__, domain))
                return None
            return fx(config)
        except (KeyError, TypeError):
            _LOGGER.error("Invalid config found for conversion to '{}'"
                          "".format(cls.__name__))
            if config is not None:
                output = json.dumps(config, indent=2)
            else:
                output = config
            _LOGGER.debug("Invalid config: {}".format(output))
            return None

    def add_item(self, key, item):
        """Add item(s) to the object."""
        if type(item) is list:
            for i in item:
                if hasattr(i, "sortkeys"):
                    i.sortkeys()
            return self[key].extend(item)
        else:
            if hasattr(item, "sortkeys"):
                item.sortkeys()
            return self[key].append(item)

    def sortkeys(self, key_order=None, delim='...'):
        """Iterate keys of OrderedDict and move to front/back as necessary."""
        # Get `keys` from self, but fallback on parent
        if key_order is None:
            try:
                key_order = self.key_order
            except AttributeError:
                try:
                    key_order = super(OrderedDict, self).key_order
                except AttributeError:
                    pass

        # Make a copy so that we're not changing the original
        key_order = key_order[:]

        # Check to see if delimiter is in `key_order`
        if delim in key_order:
            mid = key_order.index(delim)
        else:
            mid = len(key_order)

        # Reverse the front keys
        key_order[:mid] = key_order[:mid][::-1]

        # Iterate keys and move them accordingly
        for i, key in enumerate(key_order):
            # Skip delimiter and missing keys
            if i == mid or key not in self:
                continue

            # Move to front/back
            self.move_to_end(key, last=i>mid)


class Lovelace(LovelaceBase):
    """Lovelace migration class."""

    # @todo Refactor AGAIN to move all conversion to this subclass.
    class Converter(LovelaceBase):
        pass


    # @todo Implement from_config
    class View(LovelaceBase):
        """Lovelace UI view representation."""

        def __init__(self, **kwargs):
            """Init view."""
            self.key_order = ['title', 'id', 'icon', 'panel', 'theme', '...',
                              'cards']
            self.setdefault('cards', [])
            super().__init__(**kwargs)

        def add_card(self, card):
            """Add a card to the view."""
            return self.add_item("cards", card)


    # @todo Implement from_config
    class EntitiesCard(LovelaceBase):
        """Lovelove UI `entities` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', '...', 'entities']
            self.setdefault('type', 'entities')
            self.setdefault('entities', [])
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item("entities", entity)


    # @todo Implement from_config
    class EntityFilterCard(LovelaceBase):
        """Lovelove UI `entity-filter` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'entities', 'state_filter', 'card',
                         'show_empty']
            self.setdefault('type', 'entity-filter')
            self.setdefault('entities', [])
            self.setdefault('state_filter', [])
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item("entities", entity)

        def add_state_filter(self, state_filter):
            """Add a state filter to the card."""
            return self.add_item("state_filter", state_filter)


    # @todo Implement from_config
    class GlanceCard(LovelaceBase):
        """Lovelove UI `glance` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', '...', 'entities']
            self.setdefault('type', 'glance')
            self.setdefault('entities', [])
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item("entities", entity)


    class HistoryGraphCard(LovelaceBase):
        """Lovelove UI `history-graph` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', 'hours_to_show', 'refresh_interval',
                         '...', 'entities']
            self.setdefault('type', 'history-graph')
            self.setdefault('entities', [])
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item("entities", entity)

        @classmethod
        def from_history_graph_config(cls, config):
            """Build the card from config."""
            return cls(title=friendly_name(config),
                       hours_to_show=config['attributes'].get('hours_to_show'),
                       refresh_interval=config['attributes'].get('refresh'),
                       entities=config['attributes']['entity_id'])


    # @todo Implement from_config
    class HorizontalStackCard(LovelaceBase):
        """Lovelove UI `horizontal-stack` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', '...', 'cards']
            self.setdefault('type', 'horizontal-stack')
            self.setdefault('cards', [])
            super().__init__(**kwargs)

        def add_card(self, card):
            """Add a card to the card."""
            return self.add_item("cards", card)


    # @todo Implement from_config
    class IframeCard(LovelaceBase):
        """Lovelove UI `iframe` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', 'url', 'aspect_ratio']
            self.setdefault('type', 'iframe')
            super().__init__(**kwargs)


    # @todo Implement from_config
    class MapCard(LovelaceBase):
        """Lovelove UI `map` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', 'aspect_ratio', '...', 'entities']
            self.setdefault('type', 'map')
            self.setdefault('entities', [])
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item("entities", entity)


    # @todo Implement from_config
    class MarkdownCard(LovelaceBase):
        """Lovelove UI `markdown` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', '...', 'content']
            self.setdefault('type', 'markdown')
            super().__init__(**kwargs)


    class MediaControlCard(LovelaceBase):
        """Lovelove UI `media-control` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'entity']
            self.setdefault('type', 'media-control')
            super().__init__(**kwargs)

        @classmethod
        def from_media_player_config(cls, config):
            """Build the card from config."""
            return cls(entity=config['entity_id'])


    # @todo Implement from_config
    class PictureCard(LovelaceBase):
        """Lovelove UI `picture` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'image', 'navigation_path', 'service', 'service_data']
            self.setdefault('type', 'picture')
            super().__init__(**kwargs)


    # @todo Implement from_config
    class PictureElementsCard(LovelaceBase):
        """Lovelove UI `picture-elements` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', 'image', 'elements']
            self.setdefault('type', 'picture-elements')
            self.setdefault('elements', [])
            super().__init__(**kwargs)

        def add_element(self, element):
            """Add an element to the card."""
            return self.add_item("elements", element)


    class PictureEntityCard(LovelaceBase):
        """Lovelove UI `picture-entity` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'entity', 'name', '...']
            self.setdefault('type', 'picture-entity')
            super().__init__(**kwargs)

        @classmethod
        def from_camera_config(cls, config):
            """Build the card from config."""
            return cls(name=friendly_name(config=config),
                       camera_image=config['entity_id'])


    # @todo Implement from_config
    class PictureGlanceCard(LovelaceBase):
        """Lovelove UI `picture-glance` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'title', '...', 'entities']
            self.setdefault('type', 'picture-glance')
            super().__init__(**kwargs)


    class PlantStatusCard(LovelaceBase):
        """Lovelove UI `plant-status` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'entity']
            self.setdefault('type', 'plant-status')
            super().__init__(**kwargs)

        @classmethod
        def from_plant_config(cls, config):
            """Build the card from config."""
            return cls(entity=config['entity_id'])


    # @todo Implement from_config
    class VerticalStackCard(LovelaceBase):
        """Lovelove UI `vertical-stack` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', '...', 'cards']
            self.setdefault('type', 'vertical-stack')
            self.setdefault('cards', [])
            super().__init__(**kwargs)

        def add_card(self, card):
            """Add a card to the card."""
            return self.add_item("cards", card)


    class WeatherForecastCard(LovelaceBase):
        """Lovelove UI `weather-forecast` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self.key_order = ['type', 'entity']
            self.setdefault('type', 'weather-forecast')
            super().__init__(**kwargs)

        @classmethod
        def from_weather_config(cls, config):
            """Build the card from config."""
            return cls(entity=config['entity_id'])


    # @todo Refactor this into CARD_CLASSES and `from_config`
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

    CARD_CLASSES = {
        'camera': PictureEntityCard,
        'history_graph': HistoryGraphCard,
        'media_player': MediaControlCard,
        'plant': PlantStatusCard,
        'weather': WeatherForecastCard,
    }


    def __init__(self, groups, title="Home"):
        """Convert existing Home Assistant config to Lovelace UI."""
        self.key_order = ['title', 'excluded_entities', '...', 'views']
        self.setdefault('views', [])
        super().__init__()

        self.groups = groups
        self['title'] = title

        if 'default_view' in self.groups:
            self.add_view(self.convert_view(self.groups['default_view'],
                                            'default_view'))

        for name, conf in self.groups.items():
            if name == 'default_view':
                continue
            if not conf.get('view', False):
                continue
            self.add_view(self.convert_view(conf, name))

        # view = Lovelace.View(title="All Entities", icon='mdi:settings')
        # view.add_card(Lovelace.EntityFilterCard(
        #     card_config={'title': "All Entities"}, filter=[{}]))
        # self.add_view(view)

        self.sortkeys()

    def add_view(self, view):
        """Add a view to the UI."""
        return self.add_item("views", view)

    # @todo Eliminate this method and consolidate conversion.
    def convert_card(self, entity_id):
        """Helper to convert a card to Lovelace UI."""
        # if entity_id not in entities:
        #     _LOGGER.warning("Cannot find config for entity '{}' "
        #                     "".format(entity_id))
        #     return None

        domain, object_id = entity_id.split('.', 1)
        config = entities.get(entity_id)

        if domain == 'group':
            if entity_id not in entities:
                _LOGGER.error("Cannot find config for entity '{}' "
                                "".format(entity_id))
                return None

            # if object_id in Lovelace.AUTOMATIC_CARDS:
            #     return Lovelace.EntityFilterCard(object_id)

            return self.convert_group(self.groups[object_id], entity_id)

        if domain in self.CARD_CLASSES:
            cls = self.CARD_CLASSES[domain]
            return cls.from_config(entities.get(entity_id, {'entity_id': entity_id}))

        _LOGGER.warning("Domain '{}' is not yet supported. ({})"
                        "".format(domain, entity_id))
        return None

        _LOGGER.warning("Cannot determine card type for entity id '{}' "
                        "-- may be unsupported".format(entity_id))
        return None

    # @todo Eliminate this method and consolidate conversion.
    def convert_group(self, config, name):
        """Helper to convert a group to Lovelace UI."""
        if config.get('view', False):
            _LOGGER.warning("Cannot have view group '{}' within a group "
                            "".format(name))
            return None

        CARD_DOMAINS = ['group'] + list(Lovelace.CARD_CLASSES.keys())

        main_card = Lovelace.EntitiesCard(title=config.get(
                                          'friendly_name',
                                          friendly_name(object_id=name)))
        extra_cards = []

        for entity_id in config.get('entity_id', []):
            domain, object_id = entity_id.split('.', 1)

            if domain not in CARD_DOMAINS:
                main_card.add_entity(entity_id)
            else:
                _LOGGER.info(
                    "Cannot have entity '{}' within non-view group '{}' "
                    "-- adding as card instead".format(
                    entity_id, name))
                extra_card = self.convert_card(entity_id)
                if extra_card is not None:
                    extra_cards.append(extra_card)

        return [main_card] + extra_cards

    # @todo Eliminate this method and consolidate conversion.
    def convert_view(self, config, name):
        """Helper to convert a view to Lovelace UI."""
        view = Lovelace.View(
            title=config.get('friendly_name', friendly_name(object_id=name)),
            icon=config.get('icon'))

        for entity_id in config.get('entity_id', []):
            card = self.convert_card(entity_id)
            if card is None:
                continue
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
            self.password = self.auth()
            return self.get(endpoint=endpoint, refresh=refresh)
        else:
            request.raise_for_status()

        self.cache[endpoint] = request
        return request

    def get_config(self, **kwargs):
        """Get config from Home Assistant REST API."""
        request = self.get('/config', **kwargs)
        return request.json()

    def get_states(self, **kwargs):
        """Get states from Home Assistant REST API."""
        request = self.get('/states', **kwargs)
        return request.json()


def get_domains(states):
    """Build a list of domains/entities from states JSON."""
    domains = {}
    for d in states:
        domain = d['entity_id'].split('.', 1)[0]
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(d)
    return domains


def get_entities(states):
    """Build a list of entities from states JSON."""
    entities = {}
    for e in states:
        entities[e['entity_id']] = e
    return entities


def friendly_name(object_id=None, entity_id=None, config=None):
    """Generate a friendly name from object ID, entity ID, or config."""
    if type(object_id) is dict:
        config = object_id
        object_id = None

    if config is not None:
        try:
            return config['attributes']['friendly_name']
        except KeyError:
            entity_id = config.get('entity_id')

    if entity_id is not None:
        object_id = entity_id.split('.', 1)[1]

    return object_id.replace('_', ' ').title()


def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwargs):
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

    OrderedDumper.add_multi_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwargs)


def main():
    """Main program function."""
    global args
    global domains
    global entities

    if args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)

    try:
        from colorlog import ColoredFormatter
        logging.getLogger().handlers[0].setFormatter(ColoredFormatter(
            "%(log_color)s[%(levelname)s] %(message)s%(reset)s",
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

    # Detect input source (file, API URL, or - [stdin])
    if args.input == '-':
        # Input is stdin
        states = json.load(sys.stdin)
    elif (args.input.lower().startswith('http://') or
          args.input.lower().startswith('https://')):
        # Input is API URL
        hass = HomeAssistantAPI(args.input, args.password)

        # Get states from REST API
        states = hass.get_states()

        # Detect UI name from config if not provided via args
        if ui_name is None:
            config = hass.get_config()
            ui_name = config.get('location_name')
    else:
        # Input is file
        try:
            with open(args.input, 'r') as f:
                states = json.load(f)
        except FileNotFoundError:
            _LOGGER.error("{}: No such file".format(args.input))
            return 1
        except PermissionError:
            _LOGGER.error("{}: Permission denied".format(args.input))
            return 1

    # Build a list of domains/entities from the states
    domains = get_domains(states)
    entities = get_entities(states)

    # Set UI name if we still don't have one
    if ui_name is None:
        ui_name = 'Home'

    # Build groups dictionary to pass to Lovelace converter
    groups = {}
    for g in domains['group']:
        object_id = g['entity_id'].split('.', 1)[1]
        groups[object_id] = g.get('attributes')

    # Convert to Lovelace UI
    lovelace = Lovelace(groups, title=ui_name)
    dump = ordered_dump(lovelace, Dumper=yaml.SafeDumper,
          default_flow_style=False)

    # Output Lovelace YAML to stdout
    print(dump.strip())

    # Return with a normal exit code
    return 0


if __name__ == '__main__':
    sys.exit(main())
