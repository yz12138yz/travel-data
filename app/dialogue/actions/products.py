"""产品咨询 Action：酒店 / 景区 / 机票 / 火车票 / 汽车票 / 接送服务。"""

from __future__ import annotations

from typing import Any

from ...database import fetch_all
from .base import ActionResult, registry
from .context import (
    expand_area_ids,
    extract_hotel_type,
    extract_scenic_rating,
    extract_scenic_type,
    extract_service_type,
    extract_star_rating,
    extract_vehicle_no,
    find_area_mentions,
)

STAR_DISPLAY = {"5": "五星", "4": "四星", "3": "三星"}
HOTEL_TYPE_DISPLAY = {
    "luxury": "豪华型", "business": "商务型", "resort": "度假型", "boutique": "精品型",
}
SCENIC_RATING_DISPLAY = {"5A": "5A级", "4A": "4A级", "3A": "3A级"}
SCENIC_TYPE_DISPLAY = {
    "theme_park": "主题公园", "museum": "博物馆", "mountain": "山地景区",
    "heritage": "文化遗产", "wetland": "湿地公园", "beach": "海滨景区",
    "snow": "冰雪景区", "forest": "森林公园", "waterfall": "瀑布溪流",
    "ancient_town": "古镇古街", "religious": "宗教场所", "theme_water": "水上乐园",
    "zoo": "动物园", "botanical_garden": "植物园", "red_tourism": "红色旅游",
    "ecological": "生态景区",
}
CABIN_DISPLAY = {"economy": "经济舱", "business": "商务舱"}
SEAT_DISPLAY = {"second_class": "二等座", "first_class": "一等座", "business": "商务座"}
SERVICE_TYPE_DISPLAY = {
    "airport_pickup": "机场接机", "airport_dropoff": "机场送机",
    "charter_daily": "包车一日游", "station_transfer": "车站接送",
}


def _money(value: Any) -> str:
    return f"¥{float(value):,.2f}" if value is not None else "价格请以详情为准"


@registry.register("search_hotels")
def search_hotels(text: str = "", **_: Any) -> ActionResult:
    areas = find_area_mentions(text)
    if not areas:
        return ActionResult(
            ok=True, action="search_hotels",
            text="请问您想查询哪个城市或目的地的酒店呢？（例如：三亚有哪些酒店）",
        )
    area_ids = expand_area_ids(areas[0]["id"])
    star = extract_star_rating(text)
    htype = extract_hotel_type(text)

    conditions = ["h.status_code = 'active'",
                  f"h.area_id IN ({','.join(['%s'] * len(area_ids))})"]
    params: list[Any] = list(area_ids)
    if star:
        conditions.append("h.star_rating_code = %s")
        params.append(star)
    if htype:
        conditions.append("h.hotel_type_code = %s")
        params.append(htype)
    where = " AND ".join(conditions)
    rows = fetch_all(
        f"""
        SELECT h.id, h.hotel_name, h.hotel_type_code, h.star_rating_code, h.address,
               MIN(d.sale_price_amount) AS min_price
        FROM hotels h
        LEFT JOIN hotel_room_types rt ON rt.hotel_id = h.id AND rt.status_code = 'active'
        LEFT JOIN hotel_room_daily d ON d.room_type_id = rt.id AND d.status_code = 'active'
        WHERE {where}
        GROUP BY h.id
        ORDER BY min_price ASC
        LIMIT 5
        """,
        tuple(params),
    )
    if not rows:
        return ActionResult(ok=True, action="search_hotels", text="抱歉，没有找到符合条件的酒店，换个城市或条件试试吧。")
    lines = [f"为您找到 {areas[0]['area_name']} 的相关酒店："]
    for r in rows:
        star_txt = STAR_DISPLAY.get(r["star_rating_code"], r["star_rating_code"])
        type_txt = HOTEL_TYPE_DISPLAY.get(r["hotel_type_code"], r["hotel_type_code"])
        lines.append(
            f"- {r['hotel_name']}（{star_txt}·{type_txt}），起价 {_money(r['min_price'])}，地址：{r['address'] or '—'}"
        )
    lines.append("如需了解某家酒店的房型或预订规则，可以继续问我。")
    return ActionResult(ok=True, action="search_hotels", text="\n".join(lines),
                        data={"list": rows})


@registry.register("search_scenic")
def search_scenic(text: str = "", **_: Any) -> ActionResult:
    areas = find_area_mentions(text)
    if not areas:
        return ActionResult(
            ok=True, action="search_scenic",
            text="请问您想查询哪个城市的景点或门票呢？",
        )
    area_ids = expand_area_ids(areas[0]["id"])
    rating = extract_scenic_rating(text)
    stype = extract_scenic_type(text)
    conditions = ["s.status_code = 'active'",
                  f"s.area_id IN ({','.join(['%s'] * len(area_ids))})"]
    params: list[Any] = list(area_ids)
    if rating:
        conditions.append("s.rating_code = %s")
        params.append(rating)
    if stype:
        conditions.append("s.scenic_type_code = %s")
        params.append(stype)
    where = " AND ".join(conditions)
    rows = fetch_all(
        f"""
        SELECT s.id, s.scenic_name, s.scenic_type_code, s.rating_code, s.address,
               s.open_time, s.close_time, MIN(d.sale_price_amount) AS min_price
        FROM scenic_spots s
        LEFT JOIN scenic_ticket_types t ON t.scenic_spot_id = s.id AND t.status_code = 'active'
        LEFT JOIN scenic_ticket_daily d ON d.ticket_type_id = t.id AND d.status_code = 'active'
        WHERE {where}
        GROUP BY s.id
        ORDER BY min_price ASC
        LIMIT 5
        """,
        tuple(params),
    )
    if not rows:
        return ActionResult(ok=True, action="search_scenic", text="抱歉，没有找到符合条件的景区，换个城市或条件试试吧。")
    lines = [f"为您找到 {areas[0]['area_name']} 的相关景区："]
    for r in rows:
        rating_txt = SCENIC_RATING_DISPLAY.get(r["rating_code"], r["rating_code"])
        type_txt = SCENIC_TYPE_DISPLAY.get(r["scenic_type_code"], r["scenic_type_code"])
        open_txt = f"{r['open_time']}-{r['close_time']}" if r["open_time"] else "—"
        lines.append(
            f"- {r['scenic_name']}（{rating_txt}·{type_txt}），门票起价 {_money(r['min_price'])}，开放时间 {open_txt}"
        )
    lines.append("如需了解某个景区的票种或预订规则，可以继续问我。")
    return ActionResult(ok=True, action="search_scenic", text="\n".join(lines),
                        data={"list": rows})


def _two_cities(text: str) -> tuple[int, int] | None:
    areas = find_area_mentions(text)
    if len(areas) >= 2:
        return areas[0]["id"], areas[1]["id"]
    return None


@registry.register("search_trains")
def search_trains(text: str = "", **_: Any) -> ActionResult:
    train_no = extract_vehicle_no(text)
    if train_no:
        rows = fetch_all(
            """
            SELECT r.train_no, dep_h.hub_name AS dep_hub, arr_h.hub_name AS arr_hub,
                   r.duration_minutes, MIN(i.sale_price_amount) AS min_price,
                   GROUP_CONCAT(DISTINCT i.seat_class_code) AS seat_classes
            FROM train_routes r
            JOIN train_departures d ON d.train_route_id = r.id AND d.status_code = 'scheduled'
            JOIN train_seat_inventory i ON i.train_departure_id = d.id AND i.status_code = 'active'
            JOIN transport_hubs dep_h ON dep_h.id = r.departure_hub_id
            JOIN transport_hubs arr_h ON arr_h.id = r.arrival_hub_id
            WHERE r.train_no = %s AND r.status_code = 'active'
            GROUP BY r.id
            LIMIT 3
            """,
            (train_no,),
        )
        if not rows:
            return ActionResult(ok=True, action="search_trains",
                                text=f"抱歉，没有查询到车次 {train_no}，请确认车次号是否正确。")
        lines = [f"车次 {train_no} 相关信息："]
        for r in rows:
            seats = [SEAT_DISPLAY.get(s, s) for s in (r["seat_classes"].split(",") if r["seat_classes"] else [])]
            lines.append(
                f"- {r['dep_hub']} → {r['arr_hub']}，历时约 {r['duration_minutes']} 分钟，"
                f"最低价 {_money(r['min_price'])}，可选席位：{'/'.join(seats) or '—'}"
            )
        return ActionResult(ok=True, action="search_trains", text="\n".join(lines), data={"list": rows})

    cities = _two_cities(text)
    if not cities:
        return ActionResult(ok=True, action="search_trains",
                            text="请问您要从哪里到哪里？例如：从北京到上海的高铁。")
    rows = fetch_all(
        """
        SELECT r.train_no, dep_h.hub_name AS dep_hub, arr_h.hub_name AS arr_hub,
               r.duration_minutes, MIN(i.sale_price_amount) AS min_price
        FROM train_routes r
        JOIN train_departures d ON d.train_route_id = r.id AND d.status_code = 'scheduled'
        JOIN train_seat_inventory i ON i.train_departure_id = d.id AND i.status_code = 'active'
        JOIN transport_hubs dep_h ON dep_h.id = r.departure_hub_id
        JOIN transport_hubs arr_h ON arr_h.id = r.arrival_hub_id
        WHERE r.status_code = 'active' AND r.departure_area_id = %s AND r.arrival_area_id = %s
        GROUP BY r.id
        ORDER BY min_price ASC
        LIMIT 5
        """,
        cities,
    )
    if not rows:
        return ActionResult(ok=True, action="search_trains", text="抱歉，该区间暂未查询到火车班次。")
    lines = ["为您找到相关火车班次："]
    for r in rows:
        lines.append(
            f"- {r['train_no']}，{r['dep_hub']} → {r['arr_hub']}，历时约 {r['duration_minutes']} 分钟，最低价 {_money(r['min_price'])}"
        )
    return ActionResult(ok=True, action="search_trains", text="\n".join(lines), data={"list": rows})


@registry.register("search_flights")
def search_flights(text: str = "", **_: Any) -> ActionResult:
    cities = _two_cities(text)
    if not cities:
        return ActionResult(ok=True, action="search_flights",
                            text="请问您要从哪里飞往哪里？（例如：从北京到上海的机票）")
    rows = fetch_all(
        """
        SELECT r.flight_no, r.airline_code, dep_h.hub_name AS dep_hub, arr_h.hub_name AS arr_hub,
               r.duration_minutes, MIN(i.sale_price_amount) AS min_price,
               GROUP_CONCAT(DISTINCT i.cabin_class_code) AS cabins
        FROM flight_routes r
        JOIN flight_departures d ON d.flight_route_id = r.id AND d.status_code = 'scheduled'
        JOIN flight_cabin_inventory i ON i.flight_departure_id = d.id AND i.status_code = 'active'
        JOIN transport_hubs dep_h ON dep_h.id = r.departure_hub_id
        JOIN transport_hubs arr_h ON arr_h.id = r.arrival_hub_id
        WHERE r.status_code = 'active' AND r.departure_area_id = %s AND r.arrival_area_id = %s
        GROUP BY r.id
        ORDER BY min_price ASC
        LIMIT 5
        """,
        cities,
    )
    if not rows:
        return ActionResult(ok=True, action="search_flights", text="抱歉，该区间暂未查询到航班。")
    lines = ["为您找到相关航班："]
    for r in rows:
        cabins = [CABIN_DISPLAY.get(c, c) for c in (r["cabins"].split(",") if r["cabins"] else [])]
        lines.append(
            f"- {r['flight_no']}，{r['dep_hub']} → {r['arr_hub']}，历时约 {r['duration_minutes']} 分钟，"
            f"最低价 {_money(r['min_price'])}，可选舱位：{'/'.join(cabins) or '—'}"
        )
    return ActionResult(ok=True, action="search_flights", text="\n".join(lines), data={"list": rows})


@registry.register("search_buses")
def search_buses(text: str = "", **_: Any) -> ActionResult:
    cities = _two_cities(text)
    if not cities:
        return ActionResult(ok=True, action="search_buses",
                            text="请问您要从哪里到哪里？例如：从杭州到上海的大巴。")
    rows = fetch_all(
        """
        SELECT r.route_name, dep_h.hub_name AS dep_hub, arr_h.hub_name AS arr_hub,
               r.duration_minutes, i.sale_price_amount
        FROM bus_routes r
        JOIN bus_departures d ON d.bus_route_id = r.id AND d.status_code = 'scheduled'
        JOIN bus_seat_inventory i ON i.bus_departure_id = d.id AND i.status_code = 'active'
        JOIN transport_hubs dep_h ON dep_h.id = r.departure_hub_id
        JOIN transport_hubs arr_h ON arr_h.id = r.arrival_hub_id
        WHERE r.status_code = 'active' AND r.departure_area_id = %s AND r.arrival_area_id = %s
        GROUP BY r.id
        LIMIT 5
        """,
        cities,
    )
    if not rows:
        return ActionResult(ok=True, action="search_buses", text="抱歉，该区间暂未查询到汽车班线。")
    lines = ["为您找到相关汽车班线："]
    for r in rows:
        lines.append(
            f"- {r['route_name']}，{r['dep_hub']} → {r['arr_hub']}，历时约 {r['duration_minutes']} 分钟，票价 {_money(r['sale_price_amount'])}"
        )
    return ActionResult(ok=True, action="search_buses", text="\n".join(lines), data={"list": rows})


@registry.register("search_transfers")
def search_transfers(text: str = "", **_: Any) -> ActionResult:
    areas = find_area_mentions(text)
    if not areas:
        return ActionResult(ok=True, action="search_transfers",
                            text="请问您需要在哪个城市使用接送服务？")
    area_ids = expand_area_ids(areas[0]["id"])
    stype = extract_service_type(text)
    conditions = ["s.status_code = 'active'",
                  f"s.area_id IN ({','.join(['%s'] * len(area_ids))})"]
    params: list[Any] = list(area_ids)
    if stype:
        conditions.append("s.service_type_code = %s")
        params.append(stype)
    where = " AND ".join(conditions)
    rows = fetch_all(
        f"""
        SELECT s.id, s.service_name, s.service_type_code, s.vehicle_type_code, s.passenger_capacity
        FROM transfer_services s
        WHERE {where}
        LIMIT 5
        """,
        tuple(params),
    )
    if not rows:
        return ActionResult(ok=True, action="search_transfers", text="抱歉，该城市暂未查询到接送服务。")
    lines = [f"为您找到 {areas[0]['area_name']} 的接送服务："]
    for r in rows:
        st = SERVICE_TYPE_DISPLAY.get(r["service_type_code"], r["service_type_code"])
        lines.append(f"- {r['service_name']}（{st}，核载 {r['passenger_capacity']} 人）")
    return ActionResult(ok=True, action="search_transfers", text="\n".join(lines), data={"list": rows})


# 产品类型 -> 查询动作
PRODUCT_ACTION_MAP = {
    "hotel": "search_hotels",
    "scenic": "search_scenic",
    "flight": "search_flights",
    "train": "search_trains",
    "bus": "search_buses",
    "transfer": "search_transfers",
}


def consult_product(product_type: str, text: str) -> ActionResult:
    """按产品类型分发到对应查询动作。"""
    from .base import run_action

    action = PRODUCT_ACTION_MAP.get(product_type, "search_hotels")
    return run_action(action, text=text)
