-- The tray's logic: which icons there are, and the menu of the one asked for. A menu is
-- a tree: a submenu comes out of it, beside the row it belongs to, and a menu longer
-- than the window is shown ten rows at a time — the scene only holds the slice in view.

local WINDOW = 10

local owner = nil                -- which icon the open menu belongs to
local root = {}                  -- that menu, whole

-- Whether a list brings pictures: the rows make room for them only then.
local function count_icons(rows)
    local with = 0
    for _, r in ipairs(rows) do
        if (r.icon or "") ~= "" then with = 1 break end
    end
    return with
end

-- The ten that are in view, from row `from`.
local function look(from)
    from = math.max(0, math.min(from, #root - WINDOW))
    local rows = {}
    for k = 1, math.min(WINDOW, #root) do rows[k] = root[from + k] end
    model.rows = rows
    fact.first = from
end

local function show(menu)
    root = menu
    fact.rows_total = #root
    -- Over the whole menu, not the window: the labels do not shift as it scrolls.
    fact.with_icons = count_icons(root)
    fact.sub_open = false
    look(0)
end

if not sys.watch("tray", function(list) model.icons = list end) then
    log("this system has no tray yet")
end

on("activate", function(i)
    local it = model.icons[i + 1]
    if it then sys.call("tray.activate", it.key) end
end)

on("menu", function(i)
    local it = model.icons[i + 1]
    if not it then return end
    local ok, menu = pcall(sys.ask, "tray.menu", it.key)
    if not ok then
        -- No menu to read: let it show the menu itself, if it knows how.
        pcall(sys.call, "tray.context", it.key)
        return
    end
    owner = it
    show(menu)
    fact.menu_open = true
end)

-- The window moved: the scene says which row it is at, not how many pixels. What was
-- beside it cannot follow its row any more, so the submenu goes.
on("slid", function(from)
    look(from)
    fact.sub_open = false
end)

on("choose", function(i)
    local r = model.rows[i + 1]
    if not r then return end
    if r.children and #r.children > 0 then
        -- It has more inside: the submenu opens beside it, against that row of the window.
        model.sub = r.children
        fact.sub_row = i
        fact.sub_icons = count_icons(r.children)
        fact.sub_open = true
    else
        sys.call("tray.menu_click", owner.key, r.id)
        fact.menu_open = false
    end
end)

on("pick", function(i)
    local r = model.sub[i + 1]
    if r then sys.call("tray.menu_click", owner.key, r.id) end
    fact.sub_open = false
    fact.menu_open = false
end)
