# -*- coding: utf-8 -*-

import logging
logger = logging.getLogger('anabot')
import six

from functools import wraps
from fnmatch import fnmatchcase

from anabot.conditions import is_distro_version, is_distro_version_ge
from anabot.runtime.decorators import handle_action, handle_check, check_action_result
from anabot.runtime.default import default_handler, action_result
from anabot.runtime.functions import get_attr, getnode, getnode_scroll, getnodes, getparent, getsibling, press_key, scrollto, dump
from anabot.runtime.errors import TimeoutError
from anabot.runtime.translate import tr, gtk_tr
from anabot.runtime.installation.common import done_handler
from anabot.runtime.installation.hub.partitioning.advanced.common import schema_name
from anabot.runtime.actionresult import NotFoundResult as NotFound, ActionResultPass as Pass, ActionResultFail as Fail

import anabot.runtime.installation.hub.partitioning.advanced.details

_local_path = '/installation/hub/partitioning/advanced'
def handle_act(path, *args, **kwargs):
    return handle_action(_local_path + path, *args, **kwargs)

def handle_chck(path, *args, **kwargs):
    return handle_check(_local_path + path, *args, **kwargs)

_current_selection = None

__initialized_toggles = False
def __initialize_toggles(devices_node):
    global __initialized_toggles
    import time
    if __initialized_toggles:
        return
    for toggle in getnodes(devices_node, 'toggle button'):
        toggle.actions['activate'].do()
        time.sleep(0.5)
        toggle.actions['activate'].do()
    __initialized_toggles = True

def check_partitioning_error(app_node):
    try:
        error_bar = getnode(app_node, "info bar", tr("Error"))
        warn_icon = getnode(error_bar, "icon", tr("Warnings"))
        warn_text = getsibling(warn_icon, 1, "label")
        return (False, warn_text.text)
    except TimeoutError:
        return True

def main_view(func):
    @wraps(func)
    def wrapped(element, app_node, local_node, *args, **kwargs):
        return func(element, app_node, local_node.children[1], *args, **kwargs)
    return wrapped

@handle_act('')
def base_handler(element, app_node, local_node):
    try:
        manual_label = getnode(app_node, "label", tr("MANUAL PARTITIONING"))
        # advanced partitioning panel is second child of filler which
        # is first parent of MANUAL PARTITIONING label
        advanced_panel = getparent(manual_label, "filler")
    except TimeoutError:
        return (False, "Manual partitioning panel not found")
    except IndexError:
        return (False, "Anaconda layout has changed, the anabot needs update")
    default_handler(element, app_node, advanced_panel)
    return True

def schema_manipulate(element, app_node, local_node, check):
    schema = get_attr(element, "value")
    schema_node = None
    group_nodes = getnodes(local_node, "toggle button")
    # Find schema combo box
    for group_node in group_nodes:
        shown = True
        if not group_node.checked:
            shown = False
            group_node.actions['activate'].do()
        try:
            schema_node = getnode(group_node, "combo box")
            if schema_node.name in schema_name():
                break
        except TimeoutError:
            pass
        if not shown:
            group_node.actions['activate'].do()
    else:
        return (False, "Couldn't find combo box for partitioning schema")
    # Check selected schema
    if check:
        if schema_node.name == schema_name(schema):
            return True
        return (False, u"Different schema is set: %s" % schema_node.name)
    # Select new schema
    schema_node.click()
    getnode(schema_node, "menu item", schema_name(schema)).click()


@handle_act('/schema')
@main_view
def schema_handler(element, app_node, local_node):
    schema_manipulate(element, app_node, local_node, False)

@handle_chck('/schema')
@check_action_result
@main_view
def schema_check(element, app_node, local_node):
    return schema_manipulate(element, app_node, local_node, True)

def switch_toggle(device):
    group_node = getparent(device, "toggle button")
    group_node.actions['activate'].do()

@handle_act('/select')
def select_handler(element, app_node, local_node):
    global _current_selection
    def devs(parent, device=None, mountpoint=None):
        def dname(icon):
            return icon.parent.children[0].name
        def mpoint(icon):
            return icon.parent.children[3].name
        def check(icon):
            matches = True
            if device is not None:
                matches = fnmatchcase(dname(icon), device)
            if matches and mountpoint is not None:
                matches = fnmatchcase(mpoint(icon), mountpoint)
            return matches
        try:
            return [icon.parent.parent
                    for icon in getnodes(parent, "icon", visible=None)
                    if check(icon)]
        except TimeoutError:
            return []
    def devname(device_panel):
        return getnode(device_panel, "label", visible=None).name
    fndevice = get_attr(element, "device", None)
    mountpoint = get_attr(element, "mountpoint", None)
    devices_node = getnodes(local_node, "scroll pane")[1]
    device_required = get_attr(element, "required", "no") == "yes"
    processed = [] # remember ATK nodes instead of device names
    done = False
    _current_selection = None
    # need to initialize "node visibility", toggle all toggle buttons
    #__initialize_toggles(devices_node) - this is hopefully no longer needed
    while not done:
        done = True
        for device in devs(devices_node, fndevice, mountpoint):
            # Get mountpoint name of selected device
            device_label = getnodes(device, "label")[2].name
            device_group = getparent(device, "toggle button").name
            if len(device_label) == 0:
                # In case of missing mountpoint get device description (vda1, rhel_kvm..._swap etc.)
                device_label = getnode(device, "label").name
            if (device_group, device_label) not in processed:
                group_node = None
                switch_toggle(device)
                switch_toggle(device)
                if not device.showing:
                    switch_toggle(device)
                _current_selection = device
                scrollto(device)
                device.click()
                default_handler(element, app_node, local_node)
                processed.append((device_group, device_label))
                done = False
                break
    # Fail if device was required and no device was processed
    if device_required and not processed:
        logger.debug("Could not find device defined by: %s or %s", fndevice, mountpoint)
        return False
    return True

@handle_chck('/select')
def select_check(element, app_node, local_node):
    logger.warning("I have no idea how to implement check for select ATM")
    logger.debug("Check for select is using just result of action itself")
    return action_result(element)

@handle_act('/remove')
@handle_act('/select/remove')
def remove_handler(element, app_node, local_node):
    dialog_action = get_attr(element, "dialog", "accept")
    remove_button = getnode(local_node, "push button",
                            tr("Remove", context="GUI|Custom Partitioning"))
    remove_button.click()
    remove_dialog_context = "GUI|Custom Partitioning|Confirm Delete Dialog"
    if dialog_action == "no dialog":
        return
    elif dialog_action == "accept":
        button_text = tr("_Delete It", context=remove_dialog_context)
    elif dialog_action == "reject":
        button_text = tr("_Cancel", context=remove_dialog_context)
    else:
        return (False, "Undefined state")
    dialog_texts = []
    if is_distro_version_ge('rhel', 8, 4):
        dialog_text = tr("Are you sure you want to delete all of the data on {}?")
        dialog_text = dialog_text.format("*")
    else:
        dialog_text = tr("Are you sure you want to delete all of the data on %s?")
        dialog_text %= "*"
    dialog_texts.append(dialog_text)
    if is_distro_version_ge('rhel', 8):
        # There's different text for boot related partitions, accept is as well
        if is_distro_version_ge('rhel', 8, 4):
            dialog_text = tr("{} may be a system boot partition! Deleting it may break other operating systems. Are you sure you want to delete it?")
            dialog_text = dialog_text.format("*")
        else:
            dialog_text = tr("%s may be a system boot partition! Deleting it may break other operating systems. Are you sure you want to delete it?")
            dialog_text %= "*"
        dialog_texts.append(dialog_text)
    def correct_dialog_text(node):
        return any([
            fnmatchcase(six.u(node.name), dialog_text)
            for dialog_text in dialog_texts
        ])
    try:
        remove_dialog = getnode(app_node, "dialog")
    except:
        return (False, "No dialog appeared after pressing remove button")
    if len([ x for x in getnodes(remove_dialog, "label")
             if correct_dialog_text(x)]) != 1:
        return (False, "Different dialog appeared after pressing remove button")
    default_handler(element, app_node, remove_dialog)
    getnode(remove_dialog, "push button", button_text).click()

@handle_chck('/remove')
@handle_chck('/select/remove')
def remove_check(element, app_node, local_node):
    dialog_action = get_attr(element, "dialog", "accept")
    logger.debug("Is device dead?: %s", _current_selection.dead)
    logger.debug("Is device showing?: %s", _current_selection.showing)
    if dialog_action in ("no dialog", "accept"):
        return not _current_selection.showing
    elif dialog_action == "reject":
        return not _current_selection.dead and _current_selection.showing
    return (False, "Undefined state")

def remove_related_handler_manipulate(element, app_node, local_node, dry_run):
    check = get_attr(element, "value", "yes") == "yes"
    if is_distro_version_ge('rhel', 8, 4):
        checkbox_text = tr("Delete _all file systems which are only used by {}.",
                        context="GUI|Custom Partitioning|Confirm Delete Dialog")
        checkbox_text = checkbox_text.format("*")
    else:
        checkbox_text = tr("Delete _all file systems which are only used by %s.",
                        context="GUI|Custom Partitioning|Confirm Delete Dialog")
        checkbox_text %= "*"
    checkboxes = [x for x in getnodes(local_node, "check box")
                  if fnmatchcase(six.u(x.name), checkbox_text)]
    logger.warn("Found checkboxes: %s", repr(checkboxes))
    if len(checkboxes) != 1:
        return (False, "No or more checkboxes for removing related partitions found. Check screenshot")
    checkbox = checkboxes[0]
    if dry_run:
        return checkbox.checked == check
    if checkbox.checked != check:
        checkbox.click()

@handle_act('/remove/also_related')
@handle_act('/select/remove/also_related')
def remove_related_handler(element, app_node, local_node):
    remove_related_handler_manipulate(element, app_node, local_node, False)

@handle_chck('/remove/also_related')
@handle_chck('/select/remove/also_related')
def remove_related_check(element, app_node, local_node):
    return remove_related_handler_manipulate(element, app_node, local_node,
                                             True)

@handle_act('/rescan')
def rescan_handler(element, app_node, local_node):
    dialog_action = get_attr(element, "dialog", "accept")
    rescan_name = tr("Refresh", context="GUI|Custom Partitioning")
    rescan_button = getnode(local_node, "push button", rescan_name)
    rescan_button.click()
    rescan_dialog = getnode(app_node, "dialog", tr("RESCAN DISKS"))
    default_handler(element, app_node, rescan_dialog)
    context = "GUI|Refresh Dialog|Rescan"
    if dialog_action == "accept":
        button_text = tr("_OK", context=context)
    elif dialog_action == "reject":
        button_text = tr("_Cancel", context=context)
    else:
        return (False, "Undefined state")
    getnode(rescan_dialog, "push button", button_text).click()

@handle_act('/rescan/push_rescan')
def rescan_push_rescan_handler(element, app_node, local_node):
    rescan_text = tr("_Rescan Disks", context="GUI|Refresh Dialog|Rescan")
    rescan_button = getnode(local_node, "push button", rescan_text)
    rescan_button.click()

@handle_chck('/rescan/push_rescan')
def rescan_push_rescan_check(element, app_node, local_node):
    # check that scan was successfull
    pass

@handle_act('/autopart')
def autopart_handler(element, app_node, local_node):
    if is_distro_version_ge('rhel', 8, 4):
        autopart = getnode(local_node, "push button", tr("_Click here to create them automatically.", context="GUI|Custom Partitioning|Autopart Page"))
    else:
        autopart = getnode(local_node, "push button", tr("_Click here to create them automatically."))
    autopart.click()

@handle_act('/add')
def add_handler(element, app_node, local_node):
    accept = get_attr(element, "dialog", "accept") == "accept"
    add_button = getnode(local_node, "push button",
                         tr("Add", context="GUI|Custom Partitioning"))
    add_button.click()
    add_dialog_label = getnode(app_node, "label", tr("ADD A NEW MOUNT POINT"))
    add_dialog = getparent(add_dialog_label, "dialog")
    default_handler(element, app_node, add_dialog)
    context = "GUI|Custom Partitioning|Add Dialog"
    if accept:
        button_text = "_Add mount point"
    else:
        button_text = "_Cancel"
    button_text = tr(button_text, context=context)
    getnode(add_dialog, "push button", button_text).click()

@handle_chck('/add')
@handle_chck('/autopart')
def partitioning_check(element, app_node, local_node):
    return check_partitioning_error(app_node)

def add_mountpoint_handler_manipulate(element, app_node, local_node, dryrun):
    mountpoint = get_attr(element, "value")
    combo = getnode(local_node, "combo box")
    textfield = getnode(combo, "text")
    if not dryrun:
        textfield.typeText(mountpoint)
        if is_distro_version_ge('rhel', 8):
            # Pressing enter accepts whole dialog, see:
            # https://bugzilla.redhat.com/show_bug.cgi?id=1625603
            # press tab which should be harmless in any situation
            # and should cancel the combobox offering
            press_key('\t')
        else:
            press_key('enter')
    else:
        return textfield.text == mountpoint

@handle_act('/add/mountpoint')
def add_mountpoint_handler(element, app_node, local_node):
    add_mountpoint_handler_manipulate(element, app_node, local_node, False)

@handle_chck('/add/mountpoint')
def add_mountpoint_check(element, app_node, local_node):
    return add_mountpoint_handler_manipulate(element, app_node, local_node, True)

def add_size_handler_manipulate(element, app_node, local_node, dryrun):
    size = get_attr(element, "value")
    mountpoint = getnode(local_node, "combo box")
    # textfield for size is next to mountpoint combo box
    textfield = getsibling(mountpoint, 1, "text")
    if not dryrun:
        textfield.typeText(size)
    else:
        return textfield.text == size

@handle_act('/add/size')
def add_size_handler(element, app_node, local_node):
    add_size_handler_manipulate(element, app_node, local_node, False)

@handle_chck('/add/size')
def add_size_check(element, app_node, local_node):
    return add_size_handler_manipulate(element, app_node, local_node, True)

@handle_act('/done')
def done_handler_wrap(element, app_node, local_node):
    try:
        return done_handler(element, app_node, local_node.parent)
    except TimeoutError:
        return (False, "Didn't find visible and clickable Done button")

@handle_chck('/done')
@check_action_result
def done_check(element, app_node, local_node):
    try:
        warning_bar = getnode(local_node, 'info bar', gtk_tr('Warning'))
        return (False, "Error occured")
    except TimeoutError:
        return True
    return True

@handle_act('/summary')
def summary_handler(element, app_node, local_node):
    accept = get_attr(element, "dialog", "accept") == "accept"
    context = "GUI|Summary Dialog"
    if accept:
        button_text = "_Accept Changes"
    else:
        button_text = "_Cancel & Return to Custom Partitioning"
    button_text = tr(button_text, context=context)
    try:
        dialog = getnode(app_node, "dialog", tr("SUMMARY OF CHANGES"))
    except TimeoutError:
        return (False, "Didn't find summary dialog")
    try:
        dialog_button = getnode(dialog, "push button", button_text)
    except TimeoutError:
        return (False, "Didn't find desired button in summary dialog")
    dialog_button.click()
    return True

@handle_chck('/summary')
def summary_check(element, app_node, local_node):
    if action_result(element)[0] == False:
        return action_result(element)
    try:
        dialog = getnode(app_node, "dialog", tr("SUMMARY OF CHANGES"))
        return (False, "Summary dialog is still visible")
    except TimeoutError:
        return True

ENCRYPT_CHECKBOX_NOT_FOUND = NotFound("'Encrypt my data' checkbox'")
def encrypt_data_manipulate(element, app_node, local_node, dry_run):
    action = get_attr(element, "action", "enable")
    try:
        checkbox_text = tr("Encrypt my data.")
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

def infobar_manipulate(element, app_node, local_node, dryrun):
    try:
        infobar = getnode(app_node, "info bar")
        infobar_label = getnode(infobar, "label")
        infobar_message = infobar_label.text
    except TimeoutError:
        return NotFound("Info bar or info bar message")

    if dryrun:
        expected_message = get_attr(element, "message", "*")
        translated_message = tr(expected_message)
        if fnmatchcase(infobar_message, translated_message):
            return Pass()
        else:
            return Fail("Message in info bar '%s' doesn't match the expected message '%s'." %
                (infobar_message, translated_message))
    default_handler(element, app_node, infobar_label)
    # no action makes sense here (when dryrun == False), only a check
    return Pass()

@handle_act('/infobar')
def infobar_handler(element, app_node, local_node):
    return infobar_manipulate(element, app_node, local_node, False)

@handle_chck('/infobar')
def infobar_check(element, app_node, local_node):
    return infobar_manipulate(element, app_node, local_node, True)

def infobar_alert_manipulate(element, app_node, local_node, dryrun):
    if not dryrun:
        local_node.click()
    try:
        dialog = getnode(app_node, "alert")
    except TimeoutError:
        return Pass() if dryrun else NotFound("alert dialog")
    if dryrun:
        return Fail("Alert dialog is still visible.")
    try:
        alert_message = getnode(dialog, "label").text
        close_button = getnode(dialog, "push button", tr("_Close"))
    except TimeoutError:
        return NotFound("alert label or close button")

    expected_message = get_attr(element, "message", "*")
    expected_message = tr(expected_message)
    if fnmatchcase(alert_message, expected_message):
        result = Pass()
    else:
        result = Fail("Alert message '%s' doesn't match expected message '%s'.")

    close_button.click()
    return result

@handle_act('/infobar/alert')
def infobar_alert_handler(element, app_node, local_node):
    return infobar_alert_manipulate(element, app_node, local_node, False)

@handle_chck('/infobar/alert')
@check_action_result
def infobar_alert_check(element, app_node, local_node):
    return infobar_alert_manipulate(element, app_node, local_node, True)
