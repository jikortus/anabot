import logging
logger = logging.getLogger('anabot')

from anabot.runtime.decorators import handle_action, handle_check
from anabot.runtime.default import default_handler, action_result
from anabot.runtime.functions import get_attr, getnode, getparents
from anabot.runtime.translate import tr
from anabot.runtime.errors import TimeoutError


_local_path = '/initial_setup/subscription_manager/account_panel'
handle_act = lambda x: handle_action(_local_path + x)
handle_chck = lambda x: handle_check(_local_path + x)


@handle_act('')
def account_panel_handler(element, app_node, local_node):
    user_panel = local_node
    default_handler(element, app_node, user_panel)
    return (True, None)

@handle_chck('')
def account_panel_check(element, app_node, local_node):
    return action_result(element)

@handle_act('/login')
def username_handler(element, app_node, local_node):
    login = get_attr(element, 'value')
    login_input = getnode(local_node, 'text', 'account_login')
    login_input.actions['activate'].do()
    login_input.typeText(login)

@handle_chck('/login')
def username_chck(element, app_node, local_node):
    username = get_attr(element, 'value')
    username_input = getnode(local_node, 'text', 'account_login')
    return username_input.text == username

@handle_act('/password')
def password_handler(element, app_node, local_node):
    password = get_attr(element, 'value')
    password_input = getnode(local_node, 'password text', 'account_password')
    password_input.actions['activate'].do()
    password_input.typeText(password)

# it is not possible to get password back from the widget via ATK
# only check which makes sense is to check that password is not readable
# but it is not implemented yet (ToDo)
@handle_chck('/password')
def password_check(element, app_node, local_node):
    password = get_attr(element, 'value')
    password_input = getnode(local_node, 'password text', 'account_password')
    return password_input.text != password

@handle_act('/system_name')
def system_name_handler(element, app_node, local_node):
    name = get_attr(element, 'value')
    system_input = getnode(local_node, 'text', 'consumer_name')
    system_input.actions['activate'].do()
    system_input.typeText(name)

@handle_chck('/system_name')
def system_name_chck(element, app_node, local_node):
    name = get_attr(element, 'value')
    system_input = getnode(local_node, 'text', 'consumer_name')
    return system_input.text == name

@handle_act('/back')
def back_handler(element, app_node, local_node):
    back_button = getnode(local_node.parent.parent, "push button", tr("Back", False))
    back_button.click()

@handle_chck('/back')
def back_check(element, app_node, local_node):
    sm_panels = getnode(app_node, 'page tab list', 'register_notebook')
    try:
        login_input = getnode(sm_panels, 'text', 'account_login', visible=False)
    except TimeoutError:
        return (False, "Account panel is still visible")
    return True

@handle_act('/register')
def next_handler(element, app_node, local_node):
    next_button = getnode(local_node.parent.parent, "push button", tr("Register", False))
    next_button.click()
    # registering can last some time, so wait for progressbar to show and disappear
    try:
        getnode(local_node, 'progress bar', 'register_progressbar')
    except TimeoutError:
        #ToDo show warning that progress bar was not visible
        pass
    getnode(local_node, 'progress bar', 'register_progressbar', visible=False, timeout=float('inf'))

@handle_chck('/register')
def account_panel_back_check(element, app_node, local_node):
    sm_panels = getnode(app_node, 'page tab list', 'register_notebook')
    try:
        login_input = getnode(sm_panels, 'text', 'account_login', visible=False)
    except TimeoutError:
        return (False, "Account panel is still visible")
    return True
