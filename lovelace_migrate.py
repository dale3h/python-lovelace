"""
Migration tool for Home Assistant Lovelace UI.
"""
# @todo Decide whether or not to use monster-card for `all_xxxx` groups.

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
    '-t', '--title', metavar='<title>', default='Home',
    help="title of the Lovelace UI (default: Home)")
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
        for key, value in list(self.items()):
            if value is None:
                del self[key]

    def __setitem__(self, key, value):
        sort = key not in self.keys()
        super().__setitem__(key, value)
        if sort:
            self.sortkeys()

    @classmethod
    def from_config(cls, config):
        """
        Subclass should implement config conversion methods `from_xxx_config`:

        from_camera_config(cls, config)
        from_media_player_config(cls, config)
        from_group_config(cls, config)
        """

        def invalid_config(cls, config={}, exception=None):
            """Display an error about invalid config."""
            _LOGGER.error("Invalid config for conversion to '{}': {}"
                          "".format(cls.__name__, exception))
            if config is not None:
                output = json.dumps(config, indent=2)
            else:
                output = config
            _LOGGER.debug("Invalid config: {}".format(output))

        if 'entity_id' not in config:
            invalid_config(cls, config, "Config is missing 'entity_id'")
            return None

        entity_id = config['entity_id']
        domain, object_id = entity_id.split('.', 1)

        fx = getattr(cls, "from_" + domain + "_config", None)
        if fx is None:
            _LOGGER.error("Class '{}' does not support conversion from "
                          "'{}' config".format(cls.__name__, domain))
            return None
        return fx(config)

    def add_item(self, key, item):
        """Add item(s) to the object."""
        if item is not None:
            if key not in self.keys():
                self[key] = []
            if type(item) is list:
                self[key].extend(item)
            else:
                self[key].append(item)

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

        if key_order is None:
            return

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
            self.move_to_end(key, last=i > mid)


class Lovelace(LovelaceBase):
    """Lovelace migration class."""

    class View(LovelaceBase):
        """Lovelace UI view representation."""

        def __init__(self, **kwargs):
            """Init view."""
            self.key_order = ['title', 'id', 'icon', 'panel', 'theme', '...',
                              'cards']
            super().__init__(**kwargs)

        def add_card(self, card):
            """Add a card to the view."""
            return self.add_item('cards', card)

        @classmethod
        def from_group_config(cls, group):
            """Build the view from `group` config."""
            if not group['attributes'].get('view', False):
                return None

            view = cls(title=friendly_name(group),
                       icon=group['attributes'].get('icon'))
            cards, nocards = [], []

            for entity_id in group['attributes'].get('entity_id', []):
                config = entities.get(entity_id)
                if config is None:
                    _LOGGER.error("Entity not found: {}"
                                  "".format(entity_id))
                    continue

                card = Lovelace.Card.from_config(config)
                if type(card) is list:
                    cards.extend(card)
                elif card is not None:
                    cards.append(card)
                else:
                    nocards.append(entity_id)

            if len(nocards):
                cards = [Lovelace.EntitiesCard(entities=nocards)] + cards

            view.add_card(cards)
            return view

    class Card(LovelaceBase):
        """Lovelace UI card representation."""

        @classmethod
        def from_config(cls, config):
            """Convert a config object to Lovelace UI."""
            if config is None:
                return None

            if cls is not Lovelace.Card:
                return super().from_config(config)

            entity_id, domain, _ = eid(config)
            if domain in Lovelace.CARD_DOMAINS:
                cls = Lovelace.CARD_DOMAINS[domain]
                return cls.from_config(config)

            return None

    # @todo Implement use of this in `add_entity`
    class Entity(LovelaceBase):
        """Lovelace UI entity representation."""

        def __init__(self, **kwargs):
            """Init entity."""
            self.key_order = ['entity', 'name']
            super().__init__(**kwargs)

    class Resource(LovelaceBase):
        """Lovelace UI resource representation."""

        def __init__(self, **kwargs):
            """Init resource."""
            self.key_order = ['url', 'type']
            kwargs.setdefault('type', 'js')
            super().__init__(**kwargs)

    class EntitiesCard(Card):
        """Lovelove UI `entities` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'entities'
            self.key_order = ['type', 'title', 'show_header_toggle', '...',
                              'entities']
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item('entities', entity)

        @classmethod
        def from_group_config(cls, group):
            """Build the card from `group` config."""
            control = group['attributes'].get('control') != 'hidden'
            cards, nocards = [], []

            for entity_id in group['attributes'].get('entity_id', []):
                config = entities.get(entity_id)
                if config is None:
                    _LOGGER.error("Entity not found: {}"
                                  "".format(entity_id))
                    continue

                card = Lovelace.Card.from_config(config)
                if type(card) is list:
                    cards.extend(card)
                elif card is not None:
                    cards.append(card)
                else:
                    nocards.append(entity_id)

            if len(nocards):
                primary = cls(title=friendly_name(group),
                              show_header_toggle=control,
                              entities=nocards)
                return [primary] + cards

            return cards

    class EntityFilterCard(Card):
        """Lovelove UI `entity-filter` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'entity-filter'
            self.key_order = ['type', 'entities', 'state_filter', 'card',
                              'show_empty']
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item('entities', entity)

        def add_state_filter(self, state_filter):
            """Add a state filter to the card."""
            return self.add_item('state_filter', state_filter)

    class GlanceCard(Card):
        """Lovelove UI `glance` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'glance'
            self.key_order = ['type', 'title', '...', 'entities']
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item('entities', entity)

    class HistoryGraphCard(Card):
        """Lovelove UI `history-graph` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'history-graph'
            self.key_order = ['type', 'title', 'hours_to_show',
                              'refresh_interval', '...', 'entities']
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item('entities', entity)

        @classmethod
        def from_history_graph_config(cls, config):
            """Build the card from `history_graph` config."""
            return cls(title=friendly_name(config),
                       hours_to_show=config['attributes'].get('hours_to_show'),
                       refresh_interval=config['attributes'].get('refresh'),
                       entities=config['attributes']['entity_id'])

    class HorizontalStackCard(Card):
        """Lovelove UI `horizontal-stack` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'horizontal-stack'
            self.key_order = ['type', '...', 'cards']
            super().__init__(**kwargs)

        def add_card(self, card):
            """Add a card to the card."""
            return self.add_item('cards', card)

    class IframeCard(Card):
        """Lovelove UI `iframe` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'iframe'
            self.key_order = ['type', 'title', 'url', 'aspect_ratio']
            super().__init__(**kwargs)

    class MapCard(Card):
        """Lovelove UI `map` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'map'
            self.key_order = ['type', 'title', 'aspect_ratio', '...',
                              'entities']
            super().__init__(**kwargs)

        def add_entity(self, entity):
            """Add an entity to the card."""
            return self.add_item('entities', entity)

    class MarkdownCard(Card):
        """Lovelove UI `markdown` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'markdown'
            self.key_order = ['type', 'title', '...', 'content']
            super().__init__(**kwargs)

    class MediaControlCard(Card):
        """Lovelove UI `media-control` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'media-control'
            self.key_order = ['type', 'entity']
            super().__init__(**kwargs)

        @classmethod
        def from_media_player_config(cls, config):
            """Build the card from `media_player` config."""
            return cls(entity=config['entity_id'])

    class PictureCard(Card):
        """Lovelove UI `picture` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'picture'
            self.key_order = ['type', 'image', 'navigation_path', 'service',
                              'service_data']
            super().__init__(**kwargs)

    class PictureElementsCard(Card):
        """Lovelove UI `picture-elements` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'picture-elements'
            self.key_order = ['type', 'title', 'image', 'elements']
            super().__init__(**kwargs)

        def add_element(self, element):
            """Add an element to the card."""
            return self.add_item('elements', element)

    class PictureEntityCard(Card):
        """Lovelove UI `picture-entity` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'picture-entity'
            self.key_order = ['type', 'title', 'entity', 'camera_image',
                              'image', 'state_image', 'show_info',
                              'tap_action']
            super().__init__(**kwargs)

        @classmethod
        def from_camera_config(cls, config):
            """Build the card from `camera` config."""
            return cls(title=friendly_name(config=config),
                       entity=config['entity_id'],
                       camera_image=config['entity_id'],
                       show_info=True,
                       tap_action='dialog')

    class PictureGlanceCard(Card):
        """Lovelove UI `picture-glance` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'picture-glance'
            self.key_order = ['type', 'title', '...', 'entities']
            super().__init__(**kwargs)

    class PlantStatusCard(Card):
        """Lovelove UI `plant-status` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'plant-status'
            self.key_order = ['type', 'entity']
            super().__init__(**kwargs)

        @classmethod
        def from_plant_config(cls, config):
            """Build the card from `plant` config."""
            return cls(entity=config['entity_id'])

    class VerticalStackCard(Card):
        """Lovelove UI `vertical-stack` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'vertical-stack'
            self.key_order = ['type', '...', 'cards']
            super().__init__(**kwargs)

        def add_card(self, card):
            """Add a card to the card."""
            return self.add_item('cards', card)

    class WeatherForecastCard(Card):
        """Lovelove UI `weather-forecast` card representation."""

        def __init__(self, **kwargs):
            """Init card."""
            self['type'] = 'weather-forecast'
            self.key_order = ['type', 'entity']
            super().__init__(**kwargs)

        @classmethod
        def from_weather_config(cls, config):
            """Build the card from `weather` config."""
            return cls(entity=config['entity_id'])

    class CustomCard(Card):
        """Lovelace UI `custom` card representation."""

        def __init__(self, card_type, resource=None, key_order=None, **kwargs):
            """Init card."""
            if card_type in Lovelace.CUSTOM_CARDS:
                custom = Lovelace.CUSTOM_CARDS[card_type]
                if resource is None and 'resource' in custom:
                    resource = custom['resource']
                if key_order is None and 'key_order' in custom:
                    key_order = custom['key_order']

            self['type'] = 'custom:' + card_type
            self.key_order = key_order or ['type', '...']
            self.resource = resource
            super().__init__(**kwargs)

    # @todo Possibly move this into CARD_DOMAINS and `from_config`
    # AUTO_DOMAINS = {
    #     'all_lights': 'light',
    #     'all_automations': 'automation',
    #     'all_devices': 'device_tracker',
    #     'all_fans': 'fan',
    #     'all_locks': 'lock',
    #     'all_covers': 'cover',
    #     'all_remotes': 'remote',
    #     'all_switches': 'switch',
    #     'all_vacuum_cleaners': 'vacuum',
    #     'all_scripts': 'script',
    # }

    CARD_DOMAINS = {
        'camera': PictureEntityCard,
        'group': EntitiesCard,
        'history_graph': HistoryGraphCard,
        'media_player': MediaControlCard,
        'plant': PlantStatusCard,
        'weather': WeatherForecastCard,
    }

    CUSTOM_CARDS = {
        'monster-card': {
            'resource': 'https://cdn.rawgit.com/ciotlosm/custom-lovelace/c9465a72a2f484fce135dce86c35412f099d493f/monster-card/monster-card.js',
            'key_order': ['type', 'card', 'filter', 'when', '...']
        },
    }

    def __init__(self, states, title=None):
        """Convert existing Home Assistant config to Lovelace UI."""
        self.key_order = ['title', 'resources', 'excluded_entities',
                          '...', 'views']
        super().__init__()

        self['title'] = title or "Home"

        groups = states.get('group', {})
        views = {k: v for k, v in groups.items()
                 if v['attributes'].get('view', False)}

        if 'default_view' in views:
            self.add_view(Lovelace.View.from_config(
                views.pop('default_view')))

        for view in views.values():
            self.add_view(Lovelace.View.from_config(view))

    def add_resource(self, resource):
        """Add a resource to the UI."""
        if type(resource) is str:
            resource = Lovelace.Resource(url=resource)
        elif type(resource) is dict:
            resource = Lovelace.Resource(resource)
        return self.add_item('resources', resource)

    def add_view(self, view):
        """Add a view to the UI."""
        return self.add_item('views', view)


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


def build_states(states_dump):
    """Build a list of domains/entities from states JSON."""
    states = {}
    for entity in states_dump:
        entity_id, domain, object_id = eid(entity['entity_id'])
        if domain not in states:
            states[domain] = {}
        states[domain][object_id] = entity
    return states


def get_entities(states):
    """Build a list of entities from states JSON."""
    entities = {}
    for e in states:
        entities[e['entity_id']] = e
    return entities


def eid(entity_id=None, config=None):
    """Get entity_id parts from entity_id or config."""
    if entity_id is None and config is None:
        return None, None, None

    if hasattr(config, 'get'):
        entity_id = config.get('entity_id')
    elif hasattr(entity_id, 'get'):
        entity_id = entity_id.get('entity_id')

    domain, object_id = entity_id.split('.', 1)
    return entity_id, domain, object_id


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

    # Detect input source (file, API URL, or - [stdin])
    if args.input == '-':
        # Input is stdin
        input = json.load(sys.stdin)
    elif (args.input.lower().startswith('http://') or
          args.input.lower().startswith('https://')):
        # Input is API URL
        hass = HomeAssistantAPI(args.input, args.password)

        # Get states JSON dump from REST API
        input = hass.get_states()
    else:
        # Input is file
        try:
            with open(args.input, 'r') as f:
                input = json.load(f)
        except FileNotFoundError:
            _LOGGER.error("{}: No such file".format(args.input))
            return 1
        except PermissionError:
            _LOGGER.error("{}: Permission denied".format(args.input))
            return 1

    # Build a states object from the input
    states = build_states(input)
    # @todo Find a way for `entities` to not be global
    entities = get_entities(input)

    # Convert to Lovelace UI
    lovelace = Lovelace(states, title=args.title)
    dump = ordered_dump(lovelace, Dumper=yaml.SafeDumper,
                        default_flow_style=False)

    # Output Lovelace YAML to stdout
    print(dump.strip())

    # Return with a normal exit code
    return 0


if __name__ == '__main__':
    sys.exit(main())
