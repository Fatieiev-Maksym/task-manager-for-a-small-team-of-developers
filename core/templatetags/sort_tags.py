from django import template


register = template.Library()


def get_current_sort(context, sort_param, dir_param):
    request = context.get("request")
    if not request:
        return "", "asc", None

    current_sort = request.GET.get(sort_param, "")
    current_dir = "desc" if request.GET.get(dir_param) == "desc" else "asc"
    return current_sort, current_dir, request


@register.simple_tag(takes_context=True)
def sort_url(context, sort_key, sort_param="sort", dir_param="dir"):
    current_sort, current_dir, request = get_current_sort(context, sort_param, dir_param)
    if not request:
        return "#"

    next_dir = "desc" if current_sort == sort_key and current_dir == "asc" else "asc"
    query = request.GET.copy()
    query[sort_param] = sort_key
    query[dir_param] = next_dir
    return f"?{query.urlencode()}"


@register.simple_tag(takes_context=True)
def sort_direction_url(context, sort_key, direction, sort_param="sort", dir_param="dir"):
    _current_sort, _current_dir, request = get_current_sort(context, sort_param, dir_param)
    if not request:
        return "#"

    direction = "desc" if direction == "desc" else "asc"
    query = request.GET.copy()
    query[sort_param] = sort_key
    query[dir_param] = direction
    return f"?{query.urlencode()}"


@register.simple_tag(takes_context=True)
def sort_active_class(context, sort_key, direction, sort_param="sort", dir_param="dir"):
    current_sort, current_dir, _request = get_current_sort(context, sort_param, dir_param)
    direction = "desc" if direction == "desc" else "asc"
    if current_sort == sort_key and current_dir == direction:
        return "active"
    return ""


@register.simple_tag(takes_context=True)
def sort_column_active_class(context, sort_key, sort_param="sort", dir_param="dir"):
    current_sort, _current_dir, _request = get_current_sort(context, sort_param, dir_param)
    if current_sort == sort_key:
        return "active"
    return ""


@register.simple_tag(takes_context=True)
def sort_arrow(context, sort_key, sort_param="sort", dir_param="dir"):
    current_sort, current_dir, _request = get_current_sort(context, sort_param, dir_param)
    if current_sort == sort_key and current_dir == "desc":
        return "↓"
    return "↑"


@register.simple_tag(takes_context=True)
def sort_indicator(context, sort_key, sort_param="sort", dir_param="dir"):
    current_sort, current_dir, _request = get_current_sort(context, sort_param, dir_param)
    if current_sort != sort_key:
        return ""
    return "▼" if current_dir == "desc" else "▲"
