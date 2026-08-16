#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include "../include/engine.hpp"
#include "../include/utility_class.hpp"

namespace py = pybind11;


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
        
        .def_readonly("price_locked_by_user", &Trade::price_locked_by_user)
        .def_readonly("price_setteled_at", &Trade::price_setteled_at)
        .def_readonly("quantity", &Trade::quantity)
        .def_property_readonly("buyer_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id >> 64); })
        .def_property_readonly("buyer_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.buyer_id); })
        .def_property_readonly("seller_id_high", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id >> 64); })
        .def_property_readonly("seller_id_low", [](const Trade& t) { return static_cast<uint64_t>(t.seller_id); });
        
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
                        order->price = price;
                        order->number_of_shares = number_of_shares;
                                                
                        if (max_authorized_funds.has_value()) {
                            order->max_authorized_funds = max_authorized_funds.value();
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
            py::arg("type"),
            py::arg("is_canceled"),
            py::arg("price"),
            py::arg("number_of_shares"),
            py::arg("max_authorized_funds") = std::nullopt)

        .def("tombstone_delete", [](OrderBook& book, uint64_t order_id_high, uint64_t order_id_low)-> py::object {
            unsigned __int128 full_order_id = (static_cast<unsigned __int128>(order_id_high) << 64) | order_id_low;

            Order* canceled_order = book.tombstone_delete(full_order_id);

            if(!canceled_order){
                return py::none();
            }
            unsigned __int128 owner_id = book.metadata_vault[canceled_order->metadata_index].owner_id;
            uint64_t owner_id_high = static_cast<uint64_t>(owner_id >> 64);
            uint64_t owner_id_low = static_cast<uint64_t>(owner_id);

            py::dict result;
            result["owner_id_high"] = owner_id_high;
            result["owner_id_low"] = owner_id_low;
            result["side"] = canceled_order->side;
            result["type"] = canceled_order->type;
            result["price"] = canceled_order->price;
            result["number_of_shares"] = canceled_order->number_of_shares;
            result["is_canceled"] = canceled_order->is_canceled; 

            return result;
        },
            py::arg("order_id_high"),
            py::arg("order_id_low")
        )
        .def("get_current_bbo", &OrderBook::get_current_bbo);
        
        m.def("reset_memory", &ArenaAllocator::reset);
        m.def("cleanup_memory", &ArenaAllocator::cleanup);
}