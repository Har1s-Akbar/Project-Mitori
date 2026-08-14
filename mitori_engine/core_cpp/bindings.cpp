#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include <include/engine.hpp>
#include <include/utility_class.hpp>

namespace py = pybind11;

const uint64_t PRICE_PRECISION = 100000000;

PYBIND11_MODULE(mitori_engine, m){
    m.doc() = "Mitori Engine Python Bindings- C++ to python bridge";

    py::enum_<Side>(m, "Side")
        .value("BUY", Side::BUY)
        .value("SELL", Side::SELL);
    
    py::enum_<Type>(m, "Type")
        .value("LIMIT", Type::LIMIT)
        .value("MARKET", Type::MARKET);
        
    py::class_<Trade>(m, "Trade")
        .def_readonly("ticker", &Trade::ticker)
        .def_readonly("quantity", &Trade::quantity)
        .def_readonly("price_setteled_at", &Trade::price_setteled_at)
        .def_readonly("price_locked_by_user", &Trade::price_locked_by_user)
        .def_readonly("buyer_id", &Trade::buyer_id)
        .def_readonly("seller_id", &Trade::seller_id);

    py::class_<OrderBook>(m,"OrderBook")
        .def(py::init<std::string>())
        .def("process_order", [](OrderBook & book,
                    std::string order_id,
                    std::string order_owner_id,
                    Side side,
                    Type type,
                    bool is_canceled,
                    uint64_t price,
                    uint64_t number_of_shares,
                    std::optional<double> max_authorized_funds){
                        Order* order = ArenaAllocator::allocate();
                        order->order_id = order_id;
                        order->order_owner_id = order_owner_id;
                        order->type = type;
                        order->side = side;
                        order->number_of_shares = number_of_shares;
            
                        order->price = static_cast<uint64_t>(price * PRICE_PRECISION);
        })
}