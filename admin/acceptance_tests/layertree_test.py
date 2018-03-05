# pylint: disable=no-self-use

import pytest

from . import skip_if_ci, AbstractViewsTests
from .selenium.page import BasePage


@pytest.fixture(scope='function')
@pytest.mark.usefixtures('dbsession', 'transact')
def layertree_test_data(dbsession, transact):
    del transact

    from c2cgeoportal_commons.models.main import \
        LayerGroup, LayergroupTreeitem, LayerV1, LayerWMS, LayerWMTS, OGCServer, Theme

    layers_v1 = []
    for i in range(0, 10):
        layer_v1 = LayerV1(name='layer_v1_{}'.format(i))
        layers_v1.append(layer_v1)
        dbsession.add(layer_v1)

    layers_wms = []
    ogc_server = OGCServer(name='ogc_server')
    dbsession.add(ogc_server)
    for i in range(0, 10):
        layer_wms = LayerWMS(name='layer_wms_{}'.format(i))
        layer_wms.ogc_server = ogc_server
        layers_wms.append(layer_wms)
        dbsession.add(layer_wms)

    layers_wmts = []
    for i in range(0, 10):
        layer_wmts = LayerWMTS(name='layer_wmts_{}'.format(i))
        layer_wmts.url = 'http://localhost/wmts'
        layer_wmts.layer = layer_wmts.name
        layers_wmts.append(layer_wmts)
        dbsession.add(layer_wmts)

    groups = []
    for i in range(0, 10):
        group = LayerGroup(name='layer_group_{}'.format(i))
        groups.append(group)
        dbsession.add(group)

        for j, items in enumerate((layers_v1, layers_wms, layers_wmts)):
            dbsession.add(LayergroupTreeitem(group=group, item=items[i], ordering=j))

    # a group in a group
    dbsession.add(LayergroupTreeitem(group=groups[9], item=groups[8], ordering=3))

    themes = []
    for i in range(0, 5):
        theme = Theme(name='theme_{}'.format(i))
        themes.append(theme)
        dbsession.add(theme)

        dbsession.add(LayergroupTreeitem(group=theme, item=groups[i], ordering=0))
        dbsession.add(LayergroupTreeitem(group=theme, item=groups[i + 5], ordering=1))

    themes[0].ordering = 1
    themes[3].ordering = 2
    themes[1].ordering = 3
    themes[2].ordering = 4
    themes[4].ordering = 5

    dbsession.flush()

    yield({
        'themes': themes,
        'groups': groups,
        'layers_v1': layers_v1,
        'layers_wms': layers_wms,
        'layers_wmts': layers_wmts,
        'ogc_servers': [ogc_server]
    })


@pytest.mark.usefixtures('layertree_test_data', 'test_app')
class TestLayerTreeView(AbstractViewsTests):

    _prefix = '/layertree'

    def test_index_rendering(self, test_app, layertree_test_data):
        html = self.get(test_app).html

        # check themes are sorted by ordering
        theme_names = [list(tr.select('td')[0].stripped_strings)[0]
                       for tr in html.select('tr.theme')]
        expected = [theme.name for theme in sorted(layertree_test_data['themes'],
                                                   key=lambda theme: theme.ordering)]
        assert expected == theme_names

        # check total number of nodes
        lines = html.select('#layertree-table tr')
        nb_themes = 5
        nb_groups = 10 + 1  # group 1 in group 9
        nb_layers = nb_groups * 3
        assert nb_themes + nb_groups + nb_layers == len(lines)

    def test_edit_button(self, test_app, layertree_test_data):
        resp = self.get(test_app)

        theme = layertree_test_data['themes'][0]
        group = layertree_test_data['groups'][0]
        layer_v1 = layertree_test_data['layers_v1'][0]
        layer_wms = layertree_test_data['layers_wms'][0]
        layer_wmts = layertree_test_data['layers_wmts'][0]

        for table, item_id, path in (
            ('themes', theme.id, '_{}'.format(theme.id)),
            ('layer_groups', group.id, '_{}_{}'.format(theme.id, group.id)),
            ('layers_v1', layer_v1.id, '_{}_{}_{}'.format(theme.id, group.id, layer_v1.id)),
            ('layers_wms', layer_wms.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wms.id)),
            ('layers_wmts', layer_wmts.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wmts.id)),
        ):
            link = resp.html.select_one('tr.treegrid-{} li.action-edit a'.format(path))
            assert 'http://localhost/{}/{}'.format(table, item_id) == link['href']
            test_app.get(link['href'], status=200)

    def test_unlink_button(self, test_app, layertree_test_data):
        resp = self.get(test_app)

        theme = layertree_test_data['themes'][0]
        group = layertree_test_data['groups'][0]
        layer_v1 = layertree_test_data['layers_v1'][0]
        layer_wms = layertree_test_data['layers_wms'][0]
        layer_wmts = layertree_test_data['layers_wmts'][0]

        # no unlink on theme
        assert 0 == len(
            resp.html.select('tr.treegrid-{} li.action-unlink a'
                             .format('_{}'.format(theme.id))))

        for group_id, item_id, path in (
            (group.id, layer_wmts.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wmts.id)),
            (group.id, layer_wms.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wms.id)),
            (group.id, layer_v1.id, '_{}_{}_{}'.format(theme.id, group.id, layer_v1.id)),
            (theme.id, group.id, '_{}_{}'.format(theme.id, group.id)),
        ):
            link = resp.html.select_one('tr.treegrid-{} li.action-unlink a'.format(path))
            assert 'http://localhost/layertree/unlink/{}/{}'.format(group_id, item_id) == link['data-url']

    def test_unlink(self, test_app, layertree_test_data, dbsession):
        group = layertree_test_data['groups'][0]
        item = layertree_test_data['layers_wms'][0]

        test_app.delete('/layertree/unlink/{}/{}'.format(group.id, item.id), status=200)

        dbsession.expire_all()

        assert item not in group.children

    def test_new_button(self, test_app, layertree_test_data):
        resp = self.get(test_app)
        theme = layertree_test_data['themes'][0]
        group = layertree_test_data['groups'][0]
        ogc_server = layertree_test_data['ogc_servers'][0]
        layer_wms = layertree_test_data['layers_wms'][0]
        layer_wmts = layertree_test_data['layers_wmts'][0]
        # no new on layers
        for item_id in (layer_wmts.id, layer_wms.id):
            assert 0 == len(
                resp.html.select(
                    'tr.treegrid-{} li.action-new a'.format('_{}_{}_{}'.
                                                            format(theme.id, group.id, item_id))))
        for parent_id, path, route_table, title_name, required_fields in (
            (
                group.id,
                '_{}_{}'.format(theme.id, group.id),
                'layers_wmts',
                'WMTS',
                {
                    'url': 'http://localhost/wmts/fromtree',
                    'name': 'layer-wmts-from-tree',
                    'image_type': 'image/jpeg',
                    'layer': 'layer-wmts-from-tree'
                }
            ), (
                group.id,
                '_{}_{}'.format(theme.id, group.id),
                'layers_wms',
                'WMS',
                {
                    'ogc_server_id': ogc_server.id,
                    'name': 'layer-wms-from-tree',
                    'layer': 'layer-wms-from-tree'
                }
            ), (
                theme.id,
                '_{}'.format(theme.id),
                'layer_groups',
                'Group',
                {
                'name': 'new_name_from_layer_group'
                }
            )
        ):
            resp = self.get(test_app)
            link = resp.html.select_one('tr.treegrid-{} li.action-new a[title*="{}"]'
                                        .format(path, title_name))
            assert 'http://localhost/{}/new?parent_id={}'.format(route_table, parent_id) == link['href']
            resp = test_app.get(link['href'], status=200)
            form = resp.form
            assert form['parent_id'].value == str(parent_id)
            for required_field in required_fields:
                form[required_field] = required_fields[required_field]
            resp = form.submit('submit', 302)
            created_id = resp.follow().form['id'].value
            resp = self.get(test_app)
            assert resp.html.select('.treegrid-{}_{}'.format(path, created_id)) is not None

    @skip_if_ci
    @pytest.mark.selenium
    @pytest.mark.usefixtures('selenium', 'selenium_app', 'layertree_test_data')
    class TestLayerTreeSelenium():

        _prefix = '/layertree'

        def test_unlink(self, dbsession, selenium, selenium_app, layertree_test_data):
            base_page = BasePage(selenium)

            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions
            from selenium.webdriver.support.ui import WebDriverWait

            selenium.get(selenium_app + self._prefix)

            elem = WebDriverWait(selenium, 10).until(
                expected_conditions.element_to_be_clickable((By.ID, 'layertree-expand')))
            elem.click()

            theme = layertree_test_data['themes'][0]
            group = layertree_test_data['groups'][0]
            layer_v1 = layertree_test_data['layers_v1'][0]
            layer_wms = layertree_test_data['layers_wms'][0]
            layer_wmts = layertree_test_data['layers_wmts'][0]

            for group_id, item_id, path in (
                (group.id, layer_wmts.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wmts.id)),
                (group.id, layer_wms.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wms.id)),
                (group.id, layer_v1.id, '_{}_{}_{}'.format(theme.id, group.id, layer_v1.id)),
                (theme.id, group.id, '_{}_{}'.format(theme.id, group.id)),
            ):
                elem = WebDriverWait(selenium, 10).until(
                    expected_conditions.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        'tr.treegrid-{} button.dropdown-toggle'.format(path)
                    ))
                )
                elem.click()

                elem = WebDriverWait(selenium, 10).until(
                    expected_conditions.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        'tr.treegrid-{} li.action-unlink a'.format(path)
                    ))
                )
                expected_url = '{}/layertree/unlink/{}/{}'.format(selenium_app, group_id, item_id)
                assert expected_url == elem.get_attribute('data-url')

                base_page.click_and_confirm(elem)
                base_page.wait_jquery_to_be_active()

                from c2cgeoportal_commons.models.main import LayergroupTreeitem
                link = dbsession.query(LayergroupTreeitem). \
                    filter(LayergroupTreeitem.treegroup_id == group_id). \
                    filter(LayergroupTreeitem.treeitem_id == item_id). \
                    one_or_none()
                assert link is None

                dbsession.expire_all()
                selenium.refresh()

                from selenium.common.exceptions import NoSuchElementException
                with pytest.raises(NoSuchElementException):
                    elem = selenium.find_element_by_css_selector('tr.treegrid-{}'.format(path))

        @skip_if_ci
        @pytest.mark.selenium
        @pytest.mark.usefixtures('selenium', 'selenium_app')
        def test_delete_selenium(self, dbsession, selenium, selenium_app, layertree_test_data):
            base_page = BasePage(selenium)

            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions
            from selenium.webdriver.support.ui import WebDriverWait

            selenium.get(selenium_app + self._prefix)

            elem = WebDriverWait(selenium, 10).until(
                expected_conditions.element_to_be_clickable((By.ID, 'layertree-expand')))
            elem.click()

            theme = layertree_test_data['themes'][1]
            group = layertree_test_data['groups'][1]
            layer_v1 = layertree_test_data['layers_v1'][1]
            layer_wms = layertree_test_data['layers_wms'][1]
            layer_wmts = layertree_test_data['layers_wmts'][1]
            from c2cgeoportal_commons.models.main import LayerWMS, LayerV1, LayerWMTS, LayerGroup
            for item_id, path, model in (
                (layer_wmts.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wmts.id), LayerWMTS),
                (layer_wms.id, '_{}_{}_{}'.format(theme.id, group.id, layer_wms.id), LayerWMS),
                (layer_v1.id, '_{}_{}_{}'.format(theme.id, group.id, layer_v1.id), LayerV1),
                (group.id, '_{}_{}'.format(theme.id, group.id), LayerGroup),
            ):
                elem = WebDriverWait(selenium, 10).until(
                    expected_conditions.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        'tr.treegrid-{} button.dropdown-toggle'.format(path)
                    ))
                )
                elem.click()

                elem = WebDriverWait(selenium, 10).until(
                    expected_conditions.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        'tr.treegrid-{} li.action-delete a'.format(path)
                    ))
                )
                expected_url = '{}/layertree/delete/{}'.format(selenium_app, item_id)
                assert expected_url == elem.get_attribute('data-url')

                base_page.click_and_confirm(elem)
                base_page.wait_jquery_to_be_active()

                deleted = dbsession.query(model). \
                    filter(model.id == item_id).one_or_none()
                assert deleted is None

                dbsession.expire_all()
                selenium.refresh()

                from selenium.common.exceptions import NoSuchElementException
                with pytest.raises(NoSuchElementException):
                    elem = selenium.find_element_by_css_selector('tr.treegrid-{}'.format(path))
