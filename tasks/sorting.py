from django.db.models import Case, F, IntegerField, When

from .models import Task


STATUS_ORDER = (
    ("To Do", 0),
    ("In Progress", 1),
    ("In Review", 2),
    ("Done", 3),
)

PRIORITY_ORDER = (
    (Task.Priority.HIGH, 0),
    (Task.Priority.MEDIUM, 1),
    (Task.Priority.LOW, 2),
)

ALLOWED_TASK_SORTS = {"title", "project", "status", "priority", "assignee", "deadline"}


def get_sort_direction(direction):
    return "desc" if direction == "desc" else "asc"


def get_task_sort_context(request, sort_param="sort", dir_param="dir"):
    sort = request.GET.get(sort_param)
    direction = get_sort_direction(request.GET.get(dir_param))
    if sort not in ALLOWED_TASK_SORTS:
        sort = ""
    return {"sort": sort, "dir": direction}


def sort_expression(field_name, descending=False, nulls_last=False):
    expression = F(field_name)
    if descending:
        if nulls_last:
            return expression.desc(nulls_last=True)
        return expression.desc()
    if nulls_last:
        return expression.asc(nulls_last=True)
    return expression.asc()


def order_by_field(queryset, field_name, descending=False, nulls_last=False):
    return queryset.order_by(sort_expression(field_name, descending, nulls_last), "-created_at", "pk")


def order_by_case(queryset, annotation_name, field_lookup, values, descending=False):
    order_case = Case(
        *[When(**{field_lookup: value}, then=position) for value, position in values],
        default=99,
        output_field=IntegerField(),
    )
    order_field = f"-{annotation_name}" if descending else annotation_name
    return queryset.annotate(**{annotation_name: order_case}).order_by(order_field, "-created_at", "pk")


def apply_task_sort(queryset, sort, direction):
    if sort not in ALLOWED_TASK_SORTS:
        return queryset

    descending = direction == "desc"

    if sort == "title":
        return order_by_field(queryset, "title", descending)
    if sort == "project":
        return order_by_field(queryset, "project__name", descending)
    if sort == "status":
        return order_by_case(queryset, "_status_order", "status__name", STATUS_ORDER, descending)
    if sort == "priority":
        return order_by_case(queryset, "_priority_order", "priority", PRIORITY_ORDER, descending)
    if sort == "assignee":
        return order_by_field(queryset, "assignee__username", descending, nulls_last=True)
    if sort == "deadline":
        return order_by_field(queryset, "deadline", descending, nulls_last=True)

    return queryset
