import logging
logger = logging.getLogger('anabot')

from fnmatch import fnmatchcase

from anabot.runtime.decorators import handle_action, handle_check
from anabot.runtime.default import default_handler
from anabot.runtime.functions import get_attr, waiton, getnode, getnodes, getparent, getparents
from anabot.runtime.errors import TimeoutError
from anabot.runtime.translate import tr

from dogtail.predicate import GenericPredicate

_local_path = '/installation/hub/partitioning/advanced'
handle_act = lambda x: handle_action(_local_path + x)
handle_chck = lambda x: handle_check(_local_path + x)

@handle_act('')
def base_handler(element, app_node, local_node):
    try:
        manual_label = getnode(app_node, "label", tr("MANUAL PARTITIONING"))
        # advanced partitioning panel is second child of filler which
        # is first parent of MANUAL PARTITIONING label
        advanced_panel = getparent(manual_label, "filler").children[1]
    except TimeoutError:
        return (False, "Manual partitioning panel not found")
    except IndexError:
        return (False, "Anaconda layout has changed, the anabot needs update")
    default_handler(element, app_node, advanced_panel)
    return True

@handle_act('/schema')
def schema_handler(element, app_node, local_node):
    schemas = {
        'native' : tr("Standard Partition"),
        'btrfs' : tr("Btrfs"),
        'lvm' : tr("LVM"),
        'raid' : tr("RAID"),
        'lvm thinp' : tr("LVM Thin Provisioning")
    }
    schema = get_attr(element, "value")
    schema_node = None
    group_nodes = getnodes(local_node, "toggle button")
    for group_node in group_nodes:
        shown = True
        if not group_node.checked:
            shown = False
            group_node.actions['activate'].do()
        try:
            schema_node = waiton(group_node,
                                 [GenericPredicate(roleName="combo box",
                                                   name=name)
                                  for name in schemas.values()])
        except TimeoutError:
            if not shown:
                group_node.actions['activate'].do()
    if schema_node is None:
        return (False, "Couldn't find combo box for partitioning schema")
    schema_node.click()
    getnode(schema_node, "menu item", schemas[schema]).click()

@handle_act('/select')
def select_handler(element, app_node, local_node):
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
    processed = []
    done = False
    while not done:
        done = True
        for device in devs(local_node, fndevice, mountpoint):
            name = devname(device)
            if name not in processed:
                group_node = None
                if not device.showing:
                    group_node = getparent(device, "toggle button")
                    group_node.click()
                device.click()
                default_handler(element, app_node, local_node)
                processed.append(name)
                done = False
                break

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
    dialog_text = tr("Are you sure you want to delete all of the data on %s?")
    dialog_text %= "*"
    dialog_text = unicode(dialog_text)
    try:
        remove_dialog = getnode(app_node, "dialog")
    except:
        return (False, "No dialog appeared after pressing remove button")
    if len([ x for x in getnodes(remove_dialog, "label")
             if fnmatchcase(unicode(x.name), dialog_text)]) != 1:
        return (False, "Different dialog appeared after pressing remove button")
    default_handler(element, app_node, remove_dialog)
    getnode(remove_dialog, "push button", button_text).click()

@handle_act('/remove/also_related')
@handle_act('/select/remove/also_related')
def remove_related_handler(element, app_node, local_node):
    check = get_attr(element, "value", "yes") == "yes"
    checkbox_text = tr("Delete _all other file systems in the %s root as well.",
                       context="GUI|Custom Partitioning|Confirm Delete Dialog")
    checkbox_text %= "*"
    checkbox_text = unicode(checkbox_text)
    checkboxes = [x for x in getnodes(local_node, "check box")
                  if fnmatchcase(unicode(x.name), checkbox_text)]
    logger.warn("Found checkboxes: %s", repr(checkboxes))
    if len(checkboxes) != 1:
        return (False, "No or more checkboxes for removing related partitions found. Check screenshot")
    checkbox = checkboxes[0]
    if checkbox.checked != check:
        checkbox.click()

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

# add
# details
# autopart
# done
# summary
