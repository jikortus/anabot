# -*- coding: utf-8 -*-

import logging
logger = logging.getLogger('anabot')

from fnmatch import fnmatchcase

from anabot.runtime.decorators import handle_action, handle_check, check_action_result
from anabot.runtime.functions import get_attr, getnode, getnodes, getsibling
from anabot.runtime.errors import TimeoutError
from anabot.runtime.translate import tr
from anabot.runtime.installation.common import done_handler
from anabot.runtime.actionresult import NotFoundResult as NotFound, ActionResultPass as Pass, ActionResultFail as Fail

_local_path = '/installation/hub/partitioning/add_spec_disk'
def handle_act(path, *args, **kwargs):
    return handle_action(_local_path + path, *args, **kwargs)

def handle_chck(path, *args, **kwargs):
    return handle_check(_local_path + path, *args, **kwargs)

def select_manipulate(element, app_node, local_node, dryrun):
    name = get_attr(element, "names", "*")
    action = get_attr(element, "action", "select")

    try:
        results_label = getnode(app_node, "label", tr("Search Res_ults:", context="GUI|Installation Destination|Filter|Search"))
        table_pane = getsibling(results_label, 1, "scroll pane")
        disks_table = getnode(table_pane, "table")
    except TimeoutError as e:
        return NotFound("Results found label, table pane or disks table: %s" % e)
    cells = getnodes(disks_table, "table cell")
    column_count = len(getnodes(disks_table, "table column header"))
    # every table row has checkbox on position 0 and device name on 1
    name_cells = [
        getsibling(c, -1, "table cell") 
        for c in cells[1::column_count]
        if fnmatchcase(c.name, name)
    ]
    logger.info("Devices that match name '%s' found: '%s'" % (name, [n.name for n in name_cells]))
    for c in name_cells:
        if (action == "select") != (c.checked):
            if dryrun:
                return Fail("Checkbox status for device '%s' doesn't match required action '%s'" % (c.name, action))
            logger.info("Clicking on checkbox for device %s" % c.name)
            c.click()
    return Pass()

@handle_act('/select')
def select_handler(element, app_node, local_node):
    return select_manipulate(element, app_node, local_node, False)

@handle_chck('/select')
def select_check(element, app_node, local_node):
    return select_manipulate(element, app_node, local_node, True)

@handle_act('/done')
def done_manipulate(element, app_node, local_node):
    try:
        done_button = getnode(app_node, "push button", tr("_Done", drop_underscore=False, context="GUI|Spoke Navigation"))
    except TimeoutError:
        return NotFound("clickable Done button")
    done_button.click()
    return Pass()

@handle_chck('/done')
def done_check(element, app_node, local_node):
    try:
        getnode(app_node, "push button", tr("Add Specialized Disk"))
    except TimeoutError:
        return NotFound("Add Specialized Disk button")
    return Pass()
