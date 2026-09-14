SELECT
    orders.orderId,
    lines.orderLineId,
    products.productId,
    suppliers.supplierId,
    lines.requestedQty - lines.allocatedQty AS shortageQty
FROM fiq_orders AS orders
JOIN fiq_order_lines AS lines ON lines.orderId = orders.orderId
JOIN fiq_products AS products ON products.productId = lines.productId
JOIN fiq_suppliers AS suppliers ON suppliers.supplierId = products.supplierId
WHERE orders.status = 'Open'
  AND orders.dueAt >= '2026-09-14T00:00:00Z'
  AND orders.dueAt < '2026-09-21T00:00:00Z'
  AND lines.requestedQty > lines.allocatedQty
ORDER BY orders.orderId, lines.orderLineId;