import logging
logger = logging.getLogger('anabot')
import teres
reporter = teres.Reporter.get_reporter()

import functools
from fnmatch import fnmatchcase

from anabot.conditions import is_distro_version, is_distro_version_ge
from anabot.runtime.decorators import handle_action, handle_check, check_action_result
from anabot.runtime.default import default_handler, action_result
from anabot.runtime.functions import get_attr, getnode, getnodes, getnode_scroll, scrollto, getparent
from anabot.runtime.errors import NonexistentError, TimeoutError
from anabot.runtime.translate import tr
from anabot.variables import get_variable
from anabot.runtime.actionresult import NotFoundResult as NotFound
from anabot.runtime.actionresult import ActionResultPass as Pass, ActionResultFail as Fail
from anabot.runtime.installation.common import done_handler

# submodules
from . import advanced, luks_dialog, specialized_disks

_local_path = '/installation/hub/partitioning'
def handle_act(path, *args, **kwargs):
    return handle_action(_local_path + path, *args, **kwargs)

def handle_chck(path, *args, **kwargs):
    return handle_check(_local_path + path, *args, **kwargs)

SPOKE_SELECTOR="Installation _Destination"
if is_distro_version('rhel', 7):
    SPOKE_SELECTOR="INSTALLATION _DESTINATION"

@handle_act('')
def base_handler(element, app_node, local_node):
    partitioning_label = tr(SPOKE_SELECTOR, context="GUI|Spoke")
    partitioning = getnode_scroll(app_node, "spoke selector",
                                  partitioning_label)
    partitioning.click()
    partitioning_panel = getnode(app_node, "panel",
                                 tr("INSTALLATION DESTINATION"))
    default_handler(element, app_node, partitioning_panel)

@handle_chck('')
def base_check(element, app_node, local_node):
    try:
        getnode(app_node, "panel", tr("INSTALLATION DESTINATION"))
        return (False, "Installation destination panel is still visible.")
    except TimeoutError:
        pass
    partitioning_label = tr(SPOKE_SELECTOR, context="GUI|Spoke")
    partitioning = getnode(app_node, "spoke selector", partitioning_label,
                           visible=None)
    try:
        getnode(partitioning, "label",
                tr("Error checking storage configuration"), visible=None)
        return (False, "Error checking storage configuration")
    except TimeoutError:
        pass
    return True

# Anaconda doesn't provide enough information for ATK about disk selection
# so we need to remember the disk selection ourself.
__disk_selection = {}
def disk_manipulate(element, app_node, local_node, dryrun):
    def disk_name(node):
        return node.children[0].children[3].text
    name = get_attr(element, "name")
    action = get_attr(element, "action", "select")
    disks = getnodes(local_node, node_type="disk overview", visible=None)
    # Expected behaviour is, that when there is only one disk, it's selected.
    # When there are more disks, they are not selected.
    # This doesn't apply for interactive kickstart installation where all
    # disks are always selected. Maybe there's different behaviour while
    # ignoring drives.
    if len(__disk_selection) == 0:
        d_names = [disk_name(d) for d in disks]
        logger.debug("Found disks: %s", ",".join(d_names))
        if len(d_names) == 1 or get_variable('interactive_kickstart', '0') == '1':
            for d_name in d_names:
                __disk_selection[d_name] = True
        else:
            for d_name in d_names:
                __disk_selection[d_name] = False
    # Filter those, that match name attribute
    disks = [disk for disk in disks if fnmatchcase(disk_name(disk), name)]
    logger.debug("Filtered disks: %s", ",".join([disk_name(d) for d in disks]))
    if not disks:
        return (False, "No disk with name '%s' is available in GUI." % name)
    for disk in disks:
        if dryrun:
            # report warning
            reporter.log_info("Checking disk selection doesn't work at the moment due to https://bugzilla.redhat.com/show_bug.cgi?id=1353850")
            return True
        else:
            logger.debug("Selecting/deselecting disk: %s", disk_name(disk))
            if action == "select" and not __disk_selection[disk_name(disk)]:
                logger.debug("Clicking on disk %s.", disk_name(disk))
                scrollto(disk)
                disk.click()
                __disk_selection[disk_name(disk)] = True
            elif action == "deselect" and __disk_selection[disk_name(disk)]:
                logger.debug("Clicking on disk %s.", disk_name(disk))
                scrollto(disk)
                disk.click()
                __disk_selection[disk_name(disk)] = False
    if dryrun:
        return True

@handle_act('/disk')
def disk_handler(element, app_node, local_node):
    disk_manipulate(element, app_node, local_node, False)

@handle_chck('/disk')
def disk_check(element, app_node, local_node):
    return disk_manipulate(element, app_node, local_node, True)

# The specialized disk (de)selection code is not consistent under all circumstances,
# e. g. when re-manipulating the selected devices from the 'specialized & network disks'
# subspoke - if the code is to be reused, make sure to address that!!!

## Anaconda doesn't provide enough information for ATK about disk selection
## so we need to remember the disk selection ourself.
#__spec_disk_selection = {}
#def spec_disk_manipulate(element, app_node, local_node, dryrun):
#    def disk_name(node):
#        return node.children[0].children[3].text
#    name = get_attr(element, "name")
#    action = get_attr(element, "action", "select")
#    disks = getnodes(local_node, node_type="disk overview", visible=None)
#    # Expected behaviour is that all of the specialized disks selected
#    # in the specialized & network disks dialog are selected by default
#    # Maybe there's different behaviour in kickstart while ignoring drives.
#    if len(__spec_disk_selection) == 0:
#        d_names = [disk_name(d) for d in disks]
#        for d_name in d_names:
#            __spec_disk_selection[d_name] = True
#    # Filter those that match name attribute
#    disks = [disk for disk in disks if fnmatchcase(disk_name(disk), name)]
#    logger.debug("Filtered specialized & network disks: %s", ",".join([disk_name(d) for d in disks]))
#    if not disks:
#        return (False, "No specialized & network disk with name '%s' is available in GUI." % name)
#    for disk in disks:
#        if dryrun:
#            # report warning
#            reporter.log_info("Checking specialized & network disk selection doesn't work at the moment due to https://bugzilla.redhat.com/show_bug.cgi?id=1353850")
#            return True
#        else:
#            logger.debug("Selecting/deselecting disk: %s", disk_name(disk))
#            if action == "select" and not __spec_disk_selection[disk_name(disk)]:
#                logger.debug("Clicking on disk %s.", disk_name(disk))
#                scrollto(disk)
#                disk.click()
#                __spec_disk_selection[disk_name(disk)] = True
#            elif action == "deselect" and __spec_disk_selection[disk_name(disk)]:
#                logger.debug("Clicking on disk %s.", disk_name(disk))
#                scrollto(disk)
#                disk.click()
#                __spec_disk_selection[disk_name(disk)] = False
#    if dryrun:
#        return True
#
#@handle_act('/spec_disk')
#def spec_disk_handler(element, app_node, local_node):
#    spec_disk_manipulate(element, app_node, local_node, False)
#
#@handle_chck('/spec_disk')
#def spec_disk_check(element, app_node, local_node):
#    return spec_disk_manipulate(element, app_node, local_node, True)

def add_spec_disk_manipulate(element, app_node, local_node, dryrun):
    try:
        add_button = getnode(local_node, "push button", tr("Add Specialized Disk"))
    except TimeoutError:
        return NotFound("button for adding specialized / network disks")
    if not dryrun:
        add_button.click()
        try:
            tab = getnode(app_node, "page tab", tr("Searc_h", context="GUI|Installation Destination|Filter"))
            spec_disk_panel = getparent(tab, "panel")
        except TimeoutError:
            return NotFound("specialized disk page tab or panel")
        default_handler(element, app_node, spec_disk_panel)
    return Pass()

@handle_act('/add_spec_disk')
def add_spec_disk_handler(element, app_node, local_node):
    add_spec_disk_manipulate(element, app_node, local_node, False)

@handle_chck('/add_spec_disk')
def add_spec_disk_check(element, app_node, local_node):
    return add_spec_disk_manipulate(element, app_node, local_node, True)

# RHEL-7
def mode_manipulate(element, app_node, local_node, dryrun):
    mode = get_attr(element, "mode")
    if mode == "default":
        return
    if mode == "automatic":
        radio_text = tr("A_utomatically configure partitioning.")
    if mode == "manual":
        radio_text = tr("_I will configure partitioning.")
    radio = getnode_scroll(local_node, "radio button", radio_text)
    if dryrun:
        return radio.checked
    if not radio.checked:
        radio.click()

# RHEL-8
def mode_manipulate2(element, app_node, local_node, dryrun):
    mode = get_attr(element, "mode")
    if mode == "default":
        return
    if mode == "automatic":
        radio_text = tr("A_utomatic", context="GUI|Storage")
    if mode == "manual":
        radio_text = tr("_Custom", context="GUI|Storage")
    if mode == "blivet":
        radio_text = tr("A_dvanced Custom (Blivet-GUI)", context="GUI|Storage")
    radio = getnode_scroll(local_node, "radio button", radio_text)
    if dryrun:
        return radio.checked
    if not radio.checked:
        radio.click()

@handle_act('/mode', cond=is_distro_version('rhel', 7))
def mode_handler(element, app_node, local_node):
    mode_manipulate(element, app_node, local_node, False)

@handle_chck('/mode', cond=is_distro_version('rhel', 7))
def mode_check(element, app_node, local_node):
    return mode_manipulate(element, app_node, local_node, True)

@handle_act('/mode', cond=is_distro_version_ge('rhel', 8))
def mode_handler2(element, app_node, local_node):
    mode_manipulate2(element, app_node, local_node, False)

@handle_chck('/mode', cond=is_distro_version_ge('rhel', 8))
def mode_check2(element, app_node, local_node):
    return mode_manipulate2(element, app_node, local_node, True)

def additional_space_manipulate(element, app_node, local_node, dry_run):
    action = get_attr(element, "action", "enable")
    checkbox_text = tr("I would like to _make additional space available.")
    additional_checkbox = getnode_scroll(local_node, "check box", checkbox_text)
    if not dry_run:
        if (action == "enable") != additional_checkbox.checked:
            additional_checkbox.click()
    else:
        return (action == "enable") == additional_checkbox.checked

def additional_space_manipulate2(element, app_node, local_node, dry_run):
    action = get_attr(element, "action", "enable")
    checkbox_text = tr(
        "I would like to _make additional space available.",
        context="GUI|Storage",
    )
    additional_checkbox = getnode_scroll(local_node, "check box", checkbox_text)
    if not dry_run:
        if (action == "enable") != additional_checkbox.checked:
            additional_checkbox.click()
    else:
        return (action == "enable") == additional_checkbox.checked

@handle_act('/additional_space', cond=is_distro_version('rhel', 7))
def additional_space_handler(element, app_node, local_node):
    additional_space_manipulate(element, app_node, local_node, False)

@handle_chck('/additional_space', cond=is_distro_version('rhel', 7))
def additional_space_check(element, app_node, local_node):
    return additional_space_manipulate(element, app_node, local_node, True)

@handle_act('/additional_space', cond=is_distro_version_ge('rhel', 8))
def additional_space_handler2(element, app_node, local_node):
    additional_space_manipulate2(element, app_node, local_node, False)

@handle_chck('/additional_space', cond=is_distro_version_ge('rhel', 8))
def additional_space_check2(element, app_node, local_node):
    return additional_space_manipulate2(element, app_node, local_node, True)

handle_act('/done')(done_handler)

@handle_chck('/done')
@check_action_result
def done_check(element, app_node, local_node):
    try:
        warning_bar = getnode(local_node, 'info bar', tr('Warnings'))
        return (False, "Error occured")
    except NonexistentError:
        return True

@handle_act('/reclaim')
def reclaim_handler(element, app_node, local_node):
    # TODO action=reclaim/cancel
    reclaim_dialog = None
    try:
        reclaim_dialog_label = getnode(
            app_node, "label", tr("RECLAIM DISK SPACE")
        )
    except TimeoutError:
        return (False, "Reclaim dialog label not found")
    reclaim_dialog = getparent(reclaim_dialog_label, "dialog")
    default_handler(element, app_node, reclaim_dialog)
    reclaim_button = getnode(reclaim_dialog, "push button",
                             tr("_Reclaim space", context="GUI|Reclaim Dialog"))
    reclaim_button.click()
    return True

@handle_chck('/reclaim')
def reclaim_check(element, app_node, local_node):
    return action_result(element)

@handle_act('/reclaim/delete_all')
def reclaim_delete_all_handler(element, app_node, local_node):
    try:
        delete_all_button = getnode(local_node, "push button",
                                    tr("Delete _all", context="GUI|Reclaim Dialog"))
    except TimeoutError:
        return (False, 'Didn\'t find "Delete all" button.')
    delete_all_button.click()
    return True

@handle_chck('/reclaim/delete_all')
def reclaim_delete_all_check(element, app_node, local_node):
    if action_result(element)[0] == False:
        return action_result(element)
    table = getnode(local_node, "tree table")
    counter = -1
    free_space = tr("Free space")
    for cell in getnodes(table, "table cell", visible=None):
        counter += 1
        if counter % 5 == 0:
            part_label = cell.text
        if counter % 5 == 4 and part_label != free_space and cell.text != tr("Delete"):
            return (False, "Not all disks/partitions are scheduled to be deleted")
    return True

ENCRYPT_CHECKBOX_NOT_FOUND = NotFound("'Encrypt my data' checkbox'")
def encrypt_data_manipulate(element, app_node, local_node, dry_run):
    action = get_attr(element, "action", "enable")
    try:
        checkbox_text = tr("_Encrypt my data.")
    except TimeoutError:
        return ENCRYPT_CHECKBOX_NOT_FOUND
    encrypt_checkbox = getnode_scroll(local_node, "check box", checkbox_text)
    if not dry_run:
        if ((action == "enable") != encrypt_checkbox.checked or
                (action == "disable") == encrypt_checkbox.checked):
            encrypt_checkbox.click()
    else:
        if ((action == "enable") == encrypt_checkbox.checked or
                (action == "disable") != encrypt_checkbox.checked):
            return Pass()
        else:
            return Fail("Data encryption checkbox state doesn't correspond "
                        "with required state \"%s\"" % action)

@handle_act('/encrypt_data')
def encrypt_data_handler(element, app_node, local_node):
    encrypt_data_manipulate(element, app_node, local_node, False)

@handle_chck('/encrypt_data')
def encrypt_data_check(element, app_node, local_node):
    return encrypt_data_manipulate(element, app_node, local_node, True)

