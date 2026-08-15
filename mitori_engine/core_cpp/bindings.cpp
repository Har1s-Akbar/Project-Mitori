#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include "../include/engine.hpp"
#include "../include/utility_class.hpp"

namespace py = pybind11;

const uint64_t PRICE_PRECISION = 100000000;

PYBIND11_MODULE(mitori_engine_cpp, m){
    m.doc() = "Mitori Engine Python Bindings- C++ to python bridge";
    py::enum_<Side>(m, "Side")
        .value("BUY", Side::BUY)
        .value("SELL", Side::SELL)
        .export_values();
    
    py::enum_<Type>(m, "Type")
        .value("LIMIT", Type::LIMIT)
        .value("MARKET", Type::MARKET)
        .export_values();

    py::class_<Trade>(m, "Trade")
        .def_readonly("ticker", &Trade::ticker)
        .def_property_readonly("quantity", [](const Trade& t) {
            return static_cast<uint64_t>(t.quantity) / PRICE_PRECISION;
        })
        .def_property_readonly("buyer_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id >> 64); })
        .def_property_readonly("buyer_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id); })
        .def_property_readonly("seller_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id >> 64); })
        .def_property_readonly("seller_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id); })
        
        .def_property_readonly("price_locked_by_user", &Trade::price_locked_by_user)
        .def_property_readonly("price_setteled_at", &Trade::price_setteled_at);

    py::class_<OrderBook>(m,"OrderBook")
        .def(py::init<std::string>(), py::arg("ticker"))
        .def("process_order", [](OrderBook & book,
                    uint64_t order_id_high , uint64_t order_id_low,
                    uint64_t order_owner_id_high, uint64_t order_owner_id_low,
                    Side side,
                    Type type,
                    bool is_canceled,
                    uint64_t price,
                    uint64_t number_of_shares,
                    std::optional<uint64_t> max_authorized_funds){
                        Order* order = ArenaAllocator::allocate();
                        
                        unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
                        unsigned __int128 full_owner_id = (static_cast<unsigned __int128>(order_owner_id_high) << 64) | order_owner_id_low;
                        
                        uint32_t current_meta_index = book.metadata_vault.size();
                        book.metadata_vault.push_back({full_order_id, full_owner_id});
                        
                        order->metadata_index = current_meta_index;
                        order->type = type;
                        order->side = side;
                        order->is_canceled = is_canceled;
                        
                        if (max_authorized_funds.has_value()) {
                            order->max_authorized_funds = static_cast<uint64_t>(max_authorized_funds.value() * PRICE_PRECISION);
                        } else {
                            order->max_authorized_funds = UINT64_MAX; 
                        }
                        return book.process_order(order);
        },
            py::arg("order_id_high"),
            py::arg("order_id_low"),
            py::arg("order_owner_id_high"),
            py::arg("order_owner_id_low"),
            py::arg("side"),
            py::arg("order_type"),
            py::arg("is_canceled"),
            py::arg("price"),
            py::arg("number_of_shares"),
            py::arg("max_authorized_funds") = std::nullopt)

        .def("tombstone_delete", [](OrderBook& book, uint64_t order_id_high, uint64_t order_id_low) {
            unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;
            book.tombstone_delete(full_order_id);
        },
            py::arg("order_id_high"),
            py::arg("order_id_low"))
        .def("get_current_bbo", &OrderBook::get_current_bbo);
        
        m.def("reset_memory", &ArenaAllocator::reset);
        m.def("cleanup_memory", &ArenaAllocator::cleanup);
}