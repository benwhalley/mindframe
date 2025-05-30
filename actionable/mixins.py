# --- decorator to mark an action method with required permission ---
def action_with_permission(permission, args=None):
    def decorator(func):
        func._is_action = True
        func._action_permission = permission
        func._action_args = args or []
        return func

    return decorator


# --- mixin for classes with actions ---
class ActionableObjectMixin:
    def get_action_permission(self, action_name):
        method = getattr(self, action_name, None)
        if not method or not getattr(method, "_is_action", False):
            return None
        return method._action_permission
